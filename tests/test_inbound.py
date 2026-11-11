import yaml

from app.agents.inbound import Inbound, Inquiry
from app.config import Settings
from app.safety.screen import URL
from app.store import Store
from tests.fakes import FakeGmail, FakeLLM, FakeNotion, FakeSlack, noon

S = Settings(owner_slack_user_id="UOWNER", booking_link="https://cal.example/origin")
AUTH = {"Authentication-Results": "mx.google.com; dmarc=pass"}


def make(live=True, **llm):
    st = Store()
    if live:
        st.set("sandbox:inbound", "off")
    n, g, sl = FakeNotion(), FakeGmail(), FakeSlack()
    return Inbound(store=st, notion=n, gmail=g, slack=sl, llm=FakeLLM(**llm), settings=S, now=noon), st, n, g, sl


def mail(body="We want a brand film for our clinic.", sender="jordan@northwind-dental.example", eid="m1", **kw):
    return Inquiry(source="Email", event_id=eid, sender=sender, sender_name="Jordan Lee", subject="Video inquiry", body=body,
                   thread_id=kw.pop("thread_id", "t1"), headers=kw.pop("headers", AUTH), gmail_id=eid, **kw)


def test_detailed_inquiry_creates_records_and_one_draft_to_sender():
    a, st, n, g, sl = make()
    out = a.handle(mail())
    assert out.action == "draft_created" and [d for d, _ in n.created] == ["companies", "contacts", "deals"]
    assert len(g.drafts) == 1 and g.drafts[0]["to"] == "jordan@northwind-dental.example"
    assert "Executive Producer at Origin Films" in g.drafts[0]["body"] and "better" in sl.messages[-1][1]


def test_same_event_twice_is_handled_once():
    a, st, n, g, sl = make()
    a.handle(mail()); out = a.handle(mail())
    assert out.action == "duplicate_event" and len(g.drafts) == 1


def test_sandbox_touches_nothing():
    a, st, n, g, sl = make(live=False)
    out = a.handle(mail())
    assert out.action == "sandbox" and not n.created and not g.drafts and "Sandbox" in sl.messages[-1][1]


def test_spam_gets_label_no_reply_no_record():
    a, st, n, g, sl = make(kind="spam")
    assert a.handle(mail()).action == "spam" and not n.created and not g.drafts and g.labels


def test_price_and_bot_questions_go_to_danny_without_a_draft():
    for flag in ("asks_price", "asks_if_bot"):
        a, st, n, g, sl = make(**{flag: True})
        out = a.handle(mail())
        assert out.action == "needs_danny" and not g.drafts and "Needs you" in sl.messages[-1][1]


def test_existing_client_is_never_a_new_lead():
    a, st, n, g, sl = make()
    n.companies["acme-legal.example"] = {"id": "c1", "properties": {"Status": {"type": "select", "select": {"name": "Past client"}}}}
    out = a.handle(mail(sender="sam@acme-legal.example"))
    assert out.action == "existing_client" and not n.created and not g.drafts


def test_same_person_on_second_channel_keeps_one_record():
    a, st, n, g, sl = make()
    n.contacts["jordan@northwind-dental.example"] = {"id": "k1", "properties": {}}
    n.open_deals["k1"] = [{"id": "deal1", "properties": {}}]
    out = a.handle(Inquiry(source="Typeform", event_id="tf1", sender="jordan@northwind-dental.example", body="x"))
    assert out.action == "lead_replied" and not n.created and not g.drafts


def test_reply_on_active_thread_stops_sequence():
    a, st, n, g, sl = make()
    n.deals_by_thread["t9"] = {"id": "deal9", "properties": {}}
    out = a.handle(mail(thread_id="t9", eid="m9"))
    assert out.action == "lead_replied" and not g.drafts
    assert n.pages["deal9"]["properties"]["Sequence state"]["select"]["name"] == "Stopped"


def test_autoresponders_form_copies_and_own_domain_are_skipped_before_any_model_call():
    a, st, n, g, sl = make()
    assert a.handle(mail(eid="a", headers={"Auto-Submitted": "auto-replied"})).action == "skipped_auto_or_bulk"
    assert a.handle(mail(eid="b", sender="notifications@typeform.com")).action == "skipped_internal_or_form_copy"
    assert a.handle(mail(eid="c", sender="info@originfilms.ca")).action == "skipped_internal_or_form_copy"
    assert a.llm.calls == 0 and not g.drafts


def test_typeform_address_is_flagged_unverified():
    a, st, n, g, sl = make()
    out = a.handle(Inquiry(source="Typeform", event_id="tf2", sender="new@lead.example", sender_name="New Lead", body="We want a video."))
    assert out.action == "draft_created" and any("unverified" in f for f in out.flags)


def test_bad_acknowledgement_from_model_is_dropped():
    a, st, n, g, sl = make(acknowledgement="We can do it for $500, see http://evil-example.com")
    a.handle(mail())
    assert "$" not in g.drafts[0]["body"] and "evil" not in g.drafts[0]["body"]


def test_attack_library_never_escapes_even_with_a_fully_tricked_model():
    cases = yaml.safe_load(open("attacks/library.yaml"))
    assert len(cases) >= 10
    for i, c in enumerate(cases):
        # worst case: the model noticed nothing and echoes attacker text into its one free sentence
        a, st, n, g, sl = make(instruction_like_text=False, acknowledgement=c["body"][:200])
        out = a.handle(mail(body=c["body"], eid=f"atk{i}", thread_id=f"atk{i}"))
        for d in g.drafts:
            assert d["to"] == "jordan@northwind-dental.example", c["name"]
            assert all(u.rstrip(".,)") == S.booking_link for u in URL.findall(d["body"])), c["name"]
            assert "evil" not in d["body"] and "$" not in d["body"] and "discount" not in d["body"].lower(), c["name"]
        assert out.action == "needs_danny" and not g.drafts, f"{c['name']} was not flagged: {out}"
