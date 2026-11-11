"""Gmail for booking@originfilms.ca. Reads, labels and creates DRAFTS only.
There is deliberately no send function. NOTE: not yet exercised against the
live mailbox."""
import base64
import os
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import parseaddr

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]   # read, label, draft. Sending is never called.


@dataclass
class Mail:
    id: str
    thread_id: str
    sender: str            # bare address
    sender_name: str
    subject: str
    body: str
    headers: dict = field(default_factory=dict)
    message_id_header: str = ""


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(None, refresh_token=os.environ["GMAIL_REFRESH_TOKEN"], client_id=os.environ["GMAIL_CLIENT_ID"],
                        client_secret=os.environ["GMAIL_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token",
                        scopes=SCOPES)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _text(payload) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        t = _text(part)
        if t:
            return t
    return ""


class Gmail:
    def __init__(self, service=None):
        self.svc = service or _service()

    def new_inbox_mail(self, max_results=25) -> list[Mail]:
        res = self.svc.users().messages().list(userId="me", q="in:inbox newer_than:2d -from:me", maxResults=max_results).execute()
        out = []
        for m in res.get("messages", []):
            full = self.svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
            hs = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
            name, addr = parseaddr(hs.get("From", ""))
            out.append(Mail(id=full["id"], thread_id=full["threadId"], sender=addr.lower(), sender_name=name,
                            subject=hs.get("Subject", ""), body=_text(full["payload"]) or full.get("snippet", ""),
                            headers=hs, message_id_header=hs.get("Message-ID", hs.get("Message-Id", ""))))
        return out

    def thread_has_reply_from(self, thread_id: str, addr: str, after_internal_ms: int = 0) -> bool:
        t = self.svc.users().threads().get(userId="me", id=thread_id, format="metadata", metadataHeaders=["From"]).execute()
        for m in t.get("messages", []):
            frm = next((h["value"] for h in m["payload"]["headers"] if h["name"] == "From"), "")
            if parseaddr(frm)[1].lower() == addr.lower() and int(m.get("internalDate", 0)) > after_internal_ms:
                return True
        return False

    def create_draft(self, *, to: str, subject: str, body: str, thread_id: str = "", in_reply_to: str = "") -> str:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject if subject.lower().startswith("re:") or not thread_id else f"Re: {subject}"
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {"raw": raw, **({"threadId": thread_id} if thread_id else {})}
        return self.svc.users().drafts().create(userId="me", body={"message": message}).execute()["id"]

    def add_label(self, message_id: str, label_name: str):
        labels = self.svc.users().labels().list(userId="me").execute().get("labels", [])
        lid = next((l["id"] for l in labels if l["name"] == label_name), None)
        if not lid:
            lid = self.svc.users().labels().create(userId="me", body={"name": label_name}).execute()["id"]
        self.svc.users().messages().modify(userId="me", id=message_id, body={"addLabelIds": [lid]}).execute()
