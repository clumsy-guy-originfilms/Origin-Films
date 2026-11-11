"""Inbound agent. Order of operations for every inquiry:
duplicate claim -> auto/bulk filter -> model reading -> spam gate -> existing
client and duplicate check -> log in Notion -> score -> draft first reply
(through the gate) -> tell Danny in Slack. Dependencies are passed in so the
whole flow runs in tests with fakes."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .. import notion as N
from ..config import FOLLOW_UP_BUSINESS_DAYS, OWN_DOMAINS, TYPEFORM_NOTIFICATION_DOMAINS, TZ, Settings
from ..safety.gate import Gate
from ..safety.screen import injection_hits, is_auto_or_bulk, sender_authenticated
from ..templates import render_first_reply, render_follow_up
from ..timeutil import add_business_days, in_quiet_hours, reply_clock_start

AGENT = "inbound"
SPAM_LABEL = "Agent/Suspected spam"


@dataclass
class Inquiry:
    source: str                      # "Typeform" or "Email"
    event_id: str                    # Typeform response ID or Gmail message ID
    sender: str
    sender_name: str = ""
    subject: str = ""
    body: str = ""
    received: datetime | None = None
    thread_id: str = ""
    message_id_header: str = ""
    headers: dict = field(default_factory=dict)
    gmail_id: str = ""


@dataclass
class Outcome:
    action: str                      # what happened, in a word
    detail: str = ""
    deal_id: str = ""
    draft_id: str = ""
    flags: list = field(default_factory=list)


class Inbound:
    def __init__(self, *, store, notion, gmail, slack, llm, settings: Settings, now=lambda: datetime.now(TZ)):
        self.store, self.notion, self.gmail, self.slack, self.llm, self.s, self.now = store, notion, gmail, slack, llm, settings, now
        self.gate = Gate(store, settings)

    # ------------------------------------------------------------------ entry
    def handle(self, q: Inquiry) -> Outcome:
        if self.store.paused(AGENT):
            return Outcome("paused")
        if not self.store.claim(f"{q.source}:{q.event_id}"):
            return Outcome("duplicate_event")
        domain = q.sender.split("@")[-1].lower() if "@" in q.sender else ""
        if q.source == "Email":
            if domain in OWN_DOMAINS or any(domain.endswith(d) for d in TYPEFORM_NOTIFICATION_DOMAINS):
                return Outcome("skipped_internal_or_form_copy")
            if is_auto_or_bulk(q.headers, q.subject, q.sender):
                return Outcome("skipped_auto_or_bulk")
            existing = self.notion.deal_by_thread(q.thread_id) if q.thread_id else None
            if existing:
                return self._lead_replied(existing, q)
        try:
            read = self.llm.read_inquiry(source=q.source, sender=q.sender, subject=q.subject, body=q.body)
        except Exception as e:
            self.store.log(AGENT, "error", q.event_id, after={"error": repr(e)})
            self.slack.alert(AGENT, f":warning: Could not read an inquiry from {q.sender} ({e}). Please handle it by hand.")
            return Outcome("needs_danny", detail=repr(e))

        hits = injection_hits(q.body + " " + q.subject)
        suspicious = bool(hits) or read.instruction_like_text

        # 1. spam gate: label, no reply, no record
        if read.kind in ("spam", "solicitation", "not_an_inquiry"):
            if q.gmail_id and not self.store.sandbox(AGENT):
                self.gmail.add_label(q.gmail_id, SPAM_LABEL)
            self.store.log(AGENT, "spam_labelled", q.event_id, after={"kind": read.kind, "sender": q.sender})
            return Outcome("spam", detail=read.kind)

        # 2. existing client and duplicate check
        contact = self.notion.contact_by_email(q.sender)
        company = self.notion.company_by_domain(domain) if domain and not _free_mail(domain) else None
        company_status = N.plain(company["properties"]["Status"]) if company else None
        if contact and self.notion.open_deals_for_contact(contact["id"]):
            deal = self.notion.open_deals_for_contact(contact["id"])[0]
            return self._lead_replied(deal, q, note="Same person wrote in again on another channel; kept one record.")
        if company_status in ("Active client", "Past client"):
            self.slack.alert(AGENT, f":bust_in_silhouette: *Existing client wrote in* ({q.sender}, {company_status}). "
                                    f"Not treated as a new lead and no reply drafted.\n>{read.summary}")
            self.store.log(AGENT, "existing_client", q.event_id, after={"sender": q.sender})
            return Outcome("existing_client")

        if self.store.sandbox(AGENT):
            body = self._first_reply(read)
            d = self.gate.check_draft(agent=AGENT, recipient=q.sender, inbound_sender=q.sender, thread=q.thread_id, body=body,
                                      day=self.now().date().isoformat(), recipient_verified=self._verified(q))
            would = (f"create Company/Contact/Deal (score {read.score}), then "
                     + ("draft the first reply" if d.allowed and not (read.asks_price or read.asks_if_bot or suspicious)
                        else "hand the thread to Danny without drafting"))
            self.store.log(AGENT, "sandbox", q.event_id, after={"would": would, "flags": d.flags, "injection_hits": hits})
            self.slack.alert(AGENT, f":test_tube: *Sandbox* – new {q.source} inquiry from {q.sender}. I would {would}."
                                    + (f"\nFlags: {'; '.join(d.flags + (['possible injection'] if suspicious else []))}" if d.flags or suspicious else ""))
            return Outcome("sandbox", detail=would, flags=d.flags + (["possible injection"] if suspicious else []))

        # 3. log it in Notion
        if not company and read.company_name:
            company = self.notion.create("companies", {"Company": N.title(read.company_name), "Status": N.select("Prospect"),
                                                       **({"Email domain": N.text(domain)} if domain and not _free_mail(domain) else {})}, AGENT)
        if not contact:
            contact = self.notion.create("contacts", {"Name": N.title(q.sender_name or read.first_name or q.sender),
                                                      "Email": N.email(q.sender),
                                                      **({"Company": N.rel(company["id"])} if company else {})}, AGENT)
        received = q.received or self.now()
        needs = "Price question" if read.asks_price else "Bot question" if read.asks_if_bot else "Possible injection" if suspicious else None
        deal = self.notion.create("deals", {
            "Deal name": N.title(f"{read.company_name or q.sender_name or q.sender} – inquiry"),
            "Stage": N.select("New lead"), "Source": N.select(q.source), "Lead score": N.select(read.score),
            "Score reasoning": N.text(read.score_reasoning), "Pain point": N.text(read.summary),
            "Owner": N.select("Danny" if needs else "Inbound agent"), "Needs Danny": N.check(True),
            "Needs Danny reason": N.select(needs or "Draft to approve"),
            "Inquiry received": N.dt(received), "Reply clock start": N.dt(reply_clock_start(received)),
            "Stage entered": N.dt(self.now()), "Follow-up step": N.number(0), "Sequence state": N.select("Not started"),
            "Gmail thread ID": N.text(q.thread_id), **({"Typeform response ID": N.text(q.event_id)} if q.source == "Typeform" else {}),
            "Primary contact": N.rel(contact["id"]), **({"Company": N.rel(company["id"])} if company else {})}, AGENT)

        # 4/5. price, bot or injection: no draft, hand to Danny
        lead = f"*{'A-lead' if read.score == 'A' else 'New lead'}* ({read.score}) via {q.source}: {q.sender}\n>{read.summary}"
        if needs:
            self.slack.alert(AGENT, f":rotating_light: {lead}\n*Needs you:* {needs}. No reply drafted.")
            return Outcome("needs_danny", detail=needs, deal_id=deal["id"])

        # 6. first reply as a draft, through the gate
        body = self._first_reply(read)
        d = self.gate.check_draft(agent=AGENT, recipient=q.sender, inbound_sender=q.sender, thread=q.thread_id, body=body,
                                  day=self.now().date().isoformat(), recipient_verified=self._verified(q))
        if not d.allowed:
            self.slack.alert(AGENT, f":no_entry: {lead}\nNo draft created: {'; '.join(d.reasons)}.")
            return Outcome("blocked", detail="; ".join(d.reasons), deal_id=deal["id"])
        draft_id = self.gmail.create_draft(to=q.sender, subject=q.subject or "Your inquiry to Origin Films", body=body,
                                           thread_id=q.thread_id, in_reply_to=q.message_id_header)
        self.store.record_draft(self.now().date().isoformat(), q.sender, q.thread_id, AGENT)
        self.store.log(AGENT, "draft_created", deal["id"], after={"draft_id": draft_id, "to": q.sender, "flags": d.flags})
        quiet = " (quiet hours: please send after 7 a.m.)" if in_quiet_hours(self.now()) else ""
        self.slack.alert(AGENT, f":email: {lead}\nFirst reply is in Gmail drafts{quiet}. Press Send to approve, or edit first."
                                + (f"\n:warning: {'; '.join(d.flags)}" if d.flags else "")
                                + "\nWhat could I have done better on this one?")
        return Outcome("draft_created", deal_id=deal["id"], draft_id=draft_id, flags=d.flags)

    # ------------------------------------------------------------- helpers
    def _first_reply(self, read) -> str:
        ack = read.acknowledgement
        from ..safety.screen import outgoing_violations
        if outgoing_violations(ack) or injection_hits(ack) or len(ack.split()) > 30 or "?" in ack:
            ack = ""                       # the model's one sentence failed the screen: drop it, keep the template
        return render_first_reply(read.first_name, read.detailed, ack, self.s.booking_link)

    def _verified(self, q: Inquiry) -> bool:
        return q.source == "Email" and sender_authenticated(q.headers, q.sender)

    def _lead_replied(self, deal: dict, q: Inquiry, note: str = "") -> Outcome:
        """A reply on an active deal stops the sequence and goes to Danny. One bounded action."""
        if not self.store.sandbox(AGENT):
            self.notion.update(deal["id"], {"Last inbound": N.dt(q.received or self.now()),
                                            "Last inbound channel": N.select("Email" if q.source == "Email" else "Typeform"),
                                            "Sequence state": N.select("Stopped"), "Stop reason": N.select("Lead replied"),
                                            "Needs Danny": N.check(True), "Needs Danny reason": N.select("Other")}, AGENT)
        self.slack.alert(AGENT, f":speech_balloon: *Lead replied* ({q.sender}). Follow-ups stopped; this one is yours. {note}")
        return Outcome("lead_replied", deal_id=deal["id"])

    # --------------------------------------------------------- daily sweep
    def note_sent_first_replies(self):
        """Danny pressing Send is the approval. Detect it and start the follow-up clock."""
        for deal in self.notion.query("deals", {"and": [{"property": "Stage", "select": {"equals": "New lead"}},
                                                        {"property": "Needs Danny reason", "select": {"equals": "Draft to approve"}}]}):
            p = deal["properties"]
            thread = N.plain(p["Gmail thread ID"])
            if thread and self.gmail.thread_has_reply_from(thread, "me"):
                today = self.now().date()
                self.notion.update(deal["id"], {"Stage": N.select("Contacted"), "First reply sent": N.dt(self.now()),
                                                "Stage entered": N.dt(self.now()), "Last outbound": N.dt(self.now()),
                                                "Needs Danny": N.check(False), "Sequence state": N.select("Active"),
                                                "Next follow-up due": N.dt(add_business_days(today, FOLLOW_UP_BUSINESS_DAYS[0]))}, AGENT)

    def sweep_follow_ups(self) -> list[Outcome]:
        out = []
        if self.store.paused(AGENT) or in_quiet_hours(self.now()):
            return out
        today = self.now().date()
        due = self.notion.query("deals", {"and": [{"property": "Sequence state", "select": {"equals": "Active"}},
                                                  {"property": "Next follow-up due", "date": {"on_or_before": today.isoformat()}}]})
        for deal in due:
            p = deal["properties"]
            step = int(N.plain(p["Follow-up step"]) or 0) + 1
            stage, thread = N.plain(p["Stage"]), N.plain(p["Gmail thread ID"])
            contact_ids = N.plain(p["Primary contact"])
            # cross-channel check: skip if the lead replied anywhere or the stage moved
            if stage != "Contacted" or N.plain(p["Last inbound"]):
                if not self.store.sandbox(AGENT):
                    self.notion.update(deal["id"], {"Sequence state": N.select("Stopped"),
                                                    "Stop reason": N.select("Lead replied" if N.plain(p["Last inbound"]) else "Stage changed")}, AGENT)
                out.append(Outcome("follow_up_skipped", deal_id=deal["id"]))
                continue
            if step > 4 or not contact_ids or not self.store.claim(f"followup:{deal['id']}:{step}"):
                continue
            c = self.notion._req("GET", f"/pages/{contact_ids[0]}")["properties"]
            to, first = N.plain(c["Email"]), (N.plain(c["Name"]) or "").split(" ")[0]
            body = render_follow_up(step, first, self.s.booking_link)
            d = self.gate.check_draft(agent=AGENT, recipient=to, inbound_sender=to, thread=thread, body=body,
                                      day=today.isoformat(), do_not_contact=bool(N.plain(c["Do not contact"])))
            if not d.allowed:
                out.append(Outcome("blocked", detail="; ".join(d.reasons), deal_id=deal["id"]))
                continue
            if d.sandbox:
                self.slack.alert(AGENT, f":test_tube: *Sandbox* – I would draft follow-up {step} of 4 to {to}.")
                out.append(Outcome("sandbox", deal_id=deal["id"]))
                continue
            draft_id = self.gmail.create_draft(to=to, subject="Following up", body=body, thread_id=thread)
            self.store.record_draft(today.isoformat(), to, thread, AGENT)
            nxt = add_business_days(today, FOLLOW_UP_BUSINESS_DAYS[step] - FOLLOW_UP_BUSINESS_DAYS[step - 1]) if step < 4 else None
            self.notion.update(deal["id"], {"Follow-up step": N.number(step), "Next follow-up due": N.dt(nxt),
                                            **({"Sequence state": N.select("Finished"), "Stop reason": N.select("Breakup sent"),
                                                "Stage": N.select("Nurture"), "Stage entered": N.dt(self.now())} if step == 4 else {})}, AGENT)
            self.slack.alert(AGENT, f":email: Follow-up {step} of 4 to {to} is in Gmail drafts. Press Send to approve.")
            out.append(Outcome("draft_created", deal_id=deal["id"], draft_id=draft_id))
        self.store.beat(AGENT)
        return out


def _free_mail(domain: str) -> bool:
    return domain in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "live.com", "me.com", "proton.me", "protonmail.com", "aol.com"}
