"""Thin Notion client. Every update records before/after values in the audit
store first, so routine writes can be reverted (Notion's API has no undo).
NOTE: written against Notion API version 2025-09-03 (data sources); not yet
exercised against the live workspace."""
import os

import httpx

from .config import NOTION_DS
from .store import Store

API = "https://api.notion.com/v1"


def title(v): return {"title": [{"text": {"content": v[:2000]}}]}
def text(v): return {"rich_text": [{"text": {"content": (v or "")[:2000]}}]}
def select(v): return {"select": {"name": v} if v else None}
def dt(v): return {"date": {"start": v.isoformat()} if v else None}
def check(v): return {"checkbox": bool(v)}
def number(v): return {"number": v}
def rel(*ids): return {"relation": [{"id": i} for i in ids if i]}
def email(v): return {"email": v or None}
def url(v): return {"url": v or None}


def plain(prop: dict):
    """Flatten one Notion property value to a simple Python value."""
    t = prop.get("type")
    v = prop.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v or [])
    if t in ("select", "status"):
        return v["name"] if v else None
    if t == "date":
        return v["start"] if v else None
    if t == "relation":
        return [x["id"] for x in v or []]
    return v


class Notion:
    def __init__(self, store: Store, token: str | None = None, client: httpx.Client | None = None):
        self.store = store
        self.http = client or httpx.Client(timeout=30, headers={
            "Authorization": f"Bearer {token or os.environ['NOTION_TOKEN']}",
            "Notion-Version": "2025-09-03", "Content-Type": "application/json"})

    def _req(self, method, path, **kw):
        r = self.http.request(method, API + path, **kw)
        r.raise_for_status()
        return r.json()

    def query(self, ds: str, filter: dict | None = None, page_size: int = 50) -> list[dict]:
        body = {"page_size": page_size}
        if filter:
            body["filter"] = filter
        return self._req("POST", f"/data_sources/{NOTION_DS[ds]}/query", json=body)["results"]

    def create(self, ds: str, props: dict, agent: str) -> dict:
        page = self._req("POST", "/pages", json={"parent": {"type": "data_source_id", "data_source_id": NOTION_DS[ds]},
                                                 "properties": props})
        self.store.log(agent, "notion.create", page["id"], before=None, after=props, ds=ds)
        return page

    def update(self, page_id: str, props: dict, agent: str) -> dict:
        current = self._req("GET", f"/pages/{page_id}")["properties"]
        before = {k: plain(current[k]) for k in props if k in current}
        self.store.log(agent, "notion.update", page_id, before=before, after=props)
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": props})

    # --- lookups used for duplicate and existing-client checks ---------------
    def contact_by_email(self, addr: str) -> dict | None:
        addr = addr.strip().lower()
        hits = self.query("contacts", {"or": [{"property": "Email", "email": {"equals": addr}},
                                              {"property": "Other emails", "rich_text": {"contains": addr}}]})
        return hits[0] if hits else None

    def company_by_domain(self, domain: str) -> dict | None:
        hits = self.query("companies", {"property": "Email domain", "rich_text": {"equals": domain.lower()}})
        return hits[0] if hits else None

    def open_deals_for_contact(self, contact_id: str) -> list[dict]:
        return self.query("deals", {"and": [{"property": "Primary contact", "relation": {"contains": contact_id}},
                                            {"property": "Stage", "select": {"does_not_equal": "Lost"}},
                                            {"property": "Stage", "select": {"does_not_equal": "Won"}}]})

    def deal_by_thread(self, thread_id: str) -> dict | None:
        hits = self.query("deals", {"property": "Gmail thread ID", "rich_text": {"equals": thread_id}})
        return hits[0] if hits else None
