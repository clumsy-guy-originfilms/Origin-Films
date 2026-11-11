"""Chief of Staff. Reads Notion and the store, then messages Danny. It never
approves anything and, in Phase 1, never edits a record."""
from datetime import datetime, timedelta, timezone

from .. import notion as N
from ..config import AGENTS, TZ
from ..timeutil import add_business_days

AGENT = "chief_of_staff"
HEARTBEAT_LIMIT = timedelta(hours=26)          # Inbound's daily sweep beats once a day


class ChiefOfStaff:
    def __init__(self, *, store, notion, slack, now=lambda: datetime.now(TZ)):
        self.store, self.notion, self.slack, self.now = store, notion, slack, now

    # --------------------------------------------------------------- digest
    def digest(self) -> str:
        if self.store.paused(AGENT):
            return ""
        now = self.now()
        waiting = self.notion.query("deals", {"property": "Needs Danny", "checkbox": {"equals": True}})
        a_leads = [d for d in waiting if N.plain(d["properties"]["Lead score"]) == "A"]
        cutoff = (now - timedelta(days=1)).astimezone(timezone.utc).isoformat()
        rows = self.store.audit_rows(500)
        spam = sum(1 for r in rows if r["action"] == "spam_labelled" and r["ts"] >= cutoff)
        errors = [r for r in rows[:200] if r["action"] == "error"][:5]
        lines = [f"*Daily digest – {now:%A %b %-d}*", "", f"*1. Waiting on you ({len(waiting)})*"]
        lines += [f"• {N.plain(d['properties']['Deal name'])} – {N.plain(d['properties']['Needs Danny reason']) or 'review'}" for d in waiting[:15]] or ["• Nothing waiting."]
        lines += ["", f"*2. A-leads ({len(a_leads)})*"] + ([f"• {N.plain(d['properties']['Deal name'])}" for d in a_leads] or ["• None."])
        lines += ["", f"*3. Suspected spam:* {spam} labelled recently. Please skim the “Agent/Suspected spam” label so no real lead is lost."]
        lines += ["", "*4. Agents*"]
        for a in AGENTS:
            mode = "paused" if self.store.paused(a) else "sandbox" if self.store.sandbox(a) else "live (drafts only)"
            lines.append(f"• {a}: {mode}")
        if errors:
            lines.append(f"• {len(errors)} recent errors; latest: {errors[0]['after'][:120]}")
        if now.weekday() == 0:
            week_ago = (now.date() - timedelta(days=7)).isoformat()
            lines += ["", "*Weekly scorecard*", f"• Model spend, last 7 days: ${self.store.spend_since(week_ago):.2f} (hosting is billed by Railway; check its usage page)",
                      f"• Drafts created and edits: see the Agent Activity views in Notion. With few leads a week, read counts, not percentages."]
        text = "\n".join(lines)
        self.slack.alert(AGENT, text)
        self.store.beat(AGENT)
        return text

    # ---------------------------------------------------------- stall watch
    def stall_watch(self) -> list[str]:
        """One nudge per record per limit; a second pass after the same window escalates."""
        if self.store.paused(AGENT):
            return []
        now, sent = self.now(), []

        def nudge(key, window: timedelta, text):
            first = self.store.get(f"nudge:{key}")
            if not first:
                self.store.set(f"nudge:{key}", now.isoformat())
                self.slack.alert(AGENT, f":hourglass: {text}")
                sent.append(text)
            elif not self.store.get(f"escalated:{key}") and now - datetime.fromisoformat(first) >= window:
                self.store.set(f"escalated:{key}", now.isoformat())
                self.slack.alert(AGENT, f":rotating_light: *Still stuck:* {text}")
                sent.append("ESCALATED " + text)

        for d in self.notion.query("deals", {"property": "Stage", "select": {"equals": "New lead"}}):
            p = d["properties"]
            start = N.plain(p["Reply clock start"])
            if start and not N.plain(p["First reply sent"]) and now - datetime.fromisoformat(start) > timedelta(minutes=30):
                who = "a draft is waiting for you to send" if N.plain(p["Needs Danny"]) else "no draft exists"
                nudge(f"firstreply:{d['id']}", timedelta(minutes=30), f"{N.plain(p['Deal name'])}: no first reply after 30 minutes ({who}).")
        limits = {"Call completed": (timedelta(hours=4), "call done, no summary passed on for the proposal"),
                  "Proposal drafting": (timedelta(hours=24), "proposal draft has waited 24 hours"),
                  }
        for stage, (window, why) in limits.items():
            for d in self.notion.query("deals", {"property": "Stage", "select": {"equals": stage}}):
                entered = N.plain(d["properties"]["Stage entered"])
                if entered and now - datetime.fromisoformat(entered) > window:
                    nudge(f"{stage}:{d['id']}", window, f"{N.plain(d['properties']['Deal name'])}: {why}.")
        for d in self.notion.query("deals", {"property": "Stage", "select": {"equals": "Nurture"}}):
            p = d["properties"]
            entered = N.plain(p["Stage entered"])
            if entered and not N.plain(p["Re-nurture date"]) and now.date() > add_business_days(datetime.fromisoformat(entered).date(), 3):
                nudge(f"nurture:{d['id']}", timedelta(days=3), f"{N.plain(p['Deal name'])}: parked with no re-nurture date.")
        return sent

    # ----------------------------------------------------------- heartbeats
    def check_heartbeats(self) -> list[str]:
        missed = []
        for a in AGENTS:
            if a == AGENT or self.store.paused(a):
                continue
            last = self.store.get(f"heartbeat:{a}")
            if last and self.now() - datetime.fromisoformat(last) > HEARTBEAT_LIMIT and self.store.claim(f"missed:{a}:{last}"):
                self.slack.alert(AGENT, f":red_circle: *{a} has gone quiet* (last heartbeat {last}). See RUNBOOK.md, section 2.")
                missed.append(a)
        return missed
