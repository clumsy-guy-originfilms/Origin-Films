"""Small durable store outside Notion: duplicate protection, append-only audit,
agent modes, send counters, heartbeats and spend. Agents cannot change modes;
only slack_app does, after checking the owner's Slack user ID."""
import json
from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, func, select
from sqlalchemy.exc import IntegrityError

md = MetaData()
events = Table("events", md, Column("key", String(300), primary_key=True), Column("seen_at", String(40)))
audit = Table("audit", md, Column("id", Integer, primary_key=True, autoincrement=True), Column("ts", String(40)),
              Column("agent", String(40)), Column("action", String(60)), Column("target", String(200)),
              Column("before", Text), Column("after", Text), Column("meta", Text))
state = Table("state", md, Column("key", String(100), primary_key=True), Column("value", String(200)))
drafts = Table("drafts", md, Column("id", Integer, primary_key=True, autoincrement=True), Column("day", String(10)),
               Column("recipient", String(320)), Column("thread", String(200)), Column("agent", String(40)))
spend = Table("spend", md, Column("id", Integer, primary_key=True, autoincrement=True), Column("day", String(10)),
              Column("agent", String(40)), Column("usd", Float))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, url: str = "sqlite:///:memory:"):
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.engine = create_engine(url)
        md.create_all(self.engine)

    # --- duplicate protection -------------------------------------------------
    def claim(self, key: str) -> bool:
        """True the first time a key is seen, False ever after. Written before acting."""
        try:
            with self.engine.begin() as c:
                c.execute(events.insert().values(key=key, seen_at=_now()))
            return True
        except IntegrityError:
            return False

    # --- audit (insert only; no update or delete is ever issued) ---------------
    def log(self, agent, action, target="", before=None, after=None, **meta) -> int:
        with self.engine.begin() as c:
            r = c.execute(audit.insert().values(ts=_now(), agent=agent, action=action, target=target,
                                                before=json.dumps(before), after=json.dumps(after),
                                                meta=json.dumps(meta, default=str)))
            return r.inserted_primary_key[0]

    def audit_rows(self, limit=50):
        with self.engine.begin() as c:
            return [dict(r._mapping) for r in c.execute(select(audit).order_by(audit.c.id.desc()).limit(limit))]

    # --- modes ----------------------------------------------------------------
    def get(self, key, default=None):
        with self.engine.begin() as c:
            row = c.execute(select(state.c.value).where(state.c.key == key)).first()
            return row[0] if row else default

    def set(self, key, value):
        with self.engine.begin() as c:
            if c.execute(state.update().where(state.c.key == key).values(value=str(value))).rowcount == 0:
                c.execute(state.insert().values(key=key, value=str(value)))

    def sandbox(self, agent) -> bool:
        return self.get(f"sandbox:{agent}", "on") != "off"      # every agent starts in sandbox

    def paused(self, agent) -> bool:
        return self.get("paused:all", "no") == "yes" or self.get(f"paused:{agent}", "no") == "yes"

    # --- counters ---------------------------------------------------------------
    def record_draft(self, day, recipient, thread, agent):
        with self.engine.begin() as c:
            c.execute(drafts.insert().values(day=day, recipient=recipient.lower(), thread=thread, agent=agent))

    def draft_counts(self, day, recipient, thread):
        with self.engine.begin() as c:
            def n(*w):
                return c.execute(select(func.count()).select_from(drafts).where(*w)).scalar_one()
            return {"day": n(drafts.c.day == day),
                    "recipient": n(drafts.c.day == day, drafts.c.recipient == recipient.lower()),
                    "thread": n(drafts.c.thread == thread) if thread else 0}

    def add_spend(self, day, agent, usd):
        with self.engine.begin() as c:
            c.execute(spend.insert().values(day=day, agent=agent, usd=usd))

    def spend_on(self, day) -> float:
        with self.engine.begin() as c:
            return float(c.execute(select(func.coalesce(func.sum(spend.c.usd), 0)).where(spend.c.day == day)).scalar_one())

    def spend_since(self, day) -> float:
        with self.engine.begin() as c:
            return float(c.execute(select(func.coalesce(func.sum(spend.c.usd), 0)).where(spend.c.day >= day)).scalar_one())

    def beat(self, agent):
        self.set(f"heartbeat:{agent}", _now())
