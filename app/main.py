"""Process entry point: web endpoints, timers and the Slack listener."""
import base64
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException, Request

from .config import TZ, Settings
from .store import Store

log = logging.getLogger("origin")
app = FastAPI()
S = Settings()
store = Store(S.database_url)
ctx: dict = {}


def typeform_signature_ok(secret: str, raw: bytes, header: str | None) -> bool:
    if not secret or not header:
        return False
    digest = base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(f"sha256={digest}", header)


def typeform_to_inquiry(payload: dict):
    from .agents.inbound import Inquiry
    fr = payload.get("form_response", {})
    labels = {f["id"]: f.get("title", "") for f in fr.get("definition", {}).get("fields", [])}
    email, name, lines = "", "", []
    for a in fr.get("answers", []):
        t = a.get("type")
        v = a.get(t) if t not in ("choice", "choices") else (a.get("choice", {}).get("label") or ", ".join(a.get("choices", {}).get("labels", [])))
        label = labels.get(a.get("field", {}).get("id"), "")
        if t == "email":
            email = str(v).strip().lower()
        elif not name and "name" in label.lower():
            name = str(v)
        lines.append(f"{label}: {v}")
    return Inquiry(source="Typeform", event_id=fr.get("token", ""), sender=email, sender_name=name,
                   subject="Website inquiry", body="\n".join(lines), received=datetime.now(timezone.utc))


@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(TZ).isoformat()}


@app.post("/webhooks/typeform")
async def typeform(request: Request, typeform_signature: str | None = Header(default=None)):
    raw = await request.body()
    if not typeform_signature_ok(os.getenv("TYPEFORM_WEBHOOK_SECRET", ""), raw, typeform_signature):
        raise HTTPException(401, "bad signature")
    q = typeform_to_inquiry(await request.json())
    if not q.sender or not q.event_id:
        raise HTTPException(422, "no email or response id")
    return {"action": ctx["inbound"].handle(q).action}


def _safe(fn):
    def run():
        try:
            fn()
        except Exception:
            log.exception("job failed: %s", fn.__name__)
            store.log("system", "error", fn.__name__, after={"error": "see server log"})
    return run


def poll_gmail():
    from .agents.inbound import Inquiry
    for m in ctx["gmail"].new_inbox_mail():
        ctx["inbound"].handle(Inquiry(source="Email", event_id=m.id, sender=m.sender, sender_name=m.sender_name, subject=m.subject,
                                      body=m.body, received=datetime.now(timezone.utc), thread_id=m.thread_id,
                                      message_id_header=m.message_id_header, headers=m.headers, gmail_id=m.id))
    ctx["inbound"].note_sent_first_replies()


def ping_outside():
    if os.getenv("HEALTHCHECK_PING_URL"):
        httpx.get(os.environ["HEALTHCHECK_PING_URL"], timeout=10)


@app.on_event("startup")
def start():
    if os.getenv("ORIGIN_DISABLE_STARTUP"):
        return
    from .agents.chief import ChiefOfStaff
    from .agents.inbound import Inbound
    from .gmail import Gmail
    from .llm import LLM
    from .notion import Notion
    from .slack_app import SlackOut, build
    bolt, handler = build(store, S.owner_slack_user_id)
    slack = SlackOut(bolt.client, S.owner_slack_user_id)
    notion = Notion(store)
    ctx["gmail"] = Gmail()
    ctx["inbound"] = Inbound(store=store, notion=notion, gmail=ctx["gmail"], slack=slack, llm=LLM(store, S.daily_budget_usd), settings=S)
    ctx["chief"] = ChiefOfStaff(store=store, notion=notion, slack=slack)
    sched = BackgroundScheduler(timezone=TZ)
    sched.add_job(_safe(poll_gmail), "interval", minutes=2, max_instances=1, coalesce=True)
    sched.add_job(_safe(ctx["inbound"].sweep_follow_ups), "cron", day_of_week="mon-fri", hour=7, minute=5)
    sched.add_job(_safe(ctx["chief"].digest), "cron", hour=8, minute=0)
    sched.add_job(_safe(ctx["chief"].stall_watch), "interval", minutes=10, max_instances=1, coalesce=True)
    sched.add_job(_safe(ctx["chief"].check_heartbeats), "interval", hours=1)
    sched.add_job(_safe(ping_outside), "interval", minutes=5)
    sched.start()
    handler.connect()
