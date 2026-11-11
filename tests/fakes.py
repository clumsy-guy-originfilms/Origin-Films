"""In-memory stand-ins so the agents run with no network and no credentials."""
import itertools
from datetime import datetime

from app.config import TZ
from app.llm import InquiryRead

_ids = itertools.count(1)


class FakeNotion:
    def __init__(self):
        self.pages, self.contacts, self.companies, self.deals_by_thread, self.open_deals = {}, {}, {}, {}, {}
        self.created = []

    def create(self, ds, props, agent):
        page = {"id": f"p{next(_ids)}", "properties": props, "ds": ds}
        self.pages[page["id"]] = page
        self.created.append((ds, props))
        return page

    def update(self, page_id, props, agent):
        self.pages.setdefault(page_id, {"id": page_id, "properties": {}})["properties"].update(props)

    def query(self, ds, filter=None, page_size=50): return []
    def contact_by_email(self, addr): return self.contacts.get(addr)
    def company_by_domain(self, d): return self.companies.get(d)
    def open_deals_for_contact(self, cid): return self.open_deals.get(cid, [])
    def deal_by_thread(self, t): return self.deals_by_thread.get(t)


class FakeGmail:
    def __init__(self): self.drafts, self.labels = [], []
    def create_draft(self, **kw): self.drafts.append(kw); return f"d{len(self.drafts)}"
    def add_label(self, mid, name): self.labels.append((mid, name))
    def thread_has_reply_from(self, *a, **k): return False


class FakeSlack:
    def __init__(self): self.messages = []
    def alert(self, agent, text): self.messages.append((agent, text))


class FakeLLM:
    """Returns a fixed reading; `gullible=True` simulates a model that was fully tricked."""
    def __init__(self, **over): self.over, self.calls = over, 0

    def read_inquiry(self, *, source, sender, subject, body, agent="inbound"):
        self.calls += 1
        base = dict(kind="inquiry", first_name="Jordan", company_name="Northwind Dental", summary="Wants a brand film.",
                    detailed=True, asks_price=False, asks_if_bot=False, instruction_like_text=False, score="B",
                    score_reasoning="Specific but small.", acknowledgement="A brand film for your clinic sounds like a great project.")
        base.update(self.over)
        return InquiryRead(**base)


def noon(): return datetime(2026, 11, 10, 12, 0, tzinfo=TZ)     # a Tuesday
