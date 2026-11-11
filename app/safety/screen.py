"""Code-level screens. These run whatever the model says."""
import re
from email.utils import parseaddr

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous|prior|above|earlier)", r"disregard (all |your |the )?(previous|prior|rules|instructions)",
    r"system prompt", r"you are now", r"new instructions", r"developer mode", r"act as (an? )?", r"do not tell (danny|anyone)",
    r"forward (this|all|every)", r"send (me|us) (your|the) (pricing|price list|rate card|contracts?|client list)",
    r"reply to .{0,40}@", r"\bbcc\b|\bcc\b.{0,20}@", r"approve(d)? (this|the) (draft|send)", r"turn off (the )?sandbox|leave sandbox|disable (the )?(safety|sandbox)",
    r"in your (reply|response|email)", r"include (this|the following|these) (link|url|text|line)", r"tell (them|him|her|the team) to",
    r"</?(system|assistant|instructions?)>", r"\bbase64\b", r"as (danny|the owner|your (boss|admin))",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]

MONEY = re.compile(r"(\$|\bcad\b|\busd\b|\bdollars?\b|\b\d{1,3}(,\d{3})+\b|\b\d+\s?k\b|\b\d{3,}\b|\bper (day|hour|video)\b|\bdiscount|\bfree of charge\b)", re.I)
CONTRACT = re.compile(r"\b(contract|agreement|nda|terms and conditions|guarantee[ds]?|refund|deposit|invoice)\b", re.I)
URL = re.compile(r"(https?://[^\s<>\")]+|\bwww\.[^\s<>\")]+)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def injection_hits(text: str) -> list[str]:
    return [p.pattern for p in _INJ if p.search(text or "")]


def outgoing_violations(body: str, allowed_links: tuple[str, ...] = ()) -> list[str]:
    """Problems that force a draft to Danny instead of any automatic handling."""
    v = []
    if MONEY.search(body):
        v.append("mentions money or figures")
    if CONTRACT.search(body):
        v.append("mentions contract or payment terms")
    for u in URL.findall(body):
        if not any(u.rstrip(".,)") == a.rstrip("/") or u.rstrip(".,)").rstrip("/") == a.rstrip("/") for a in allowed_links if a):
            v.append(f"link not on the allow-list: {u}")
    if EMAIL.search(body):
        v.append("contains an email address")
    return v


AUTO_SUBJECT = re.compile(r"^(auto(matic)?[- ]?reply|out of (the )?office|ooo\b|undeliverable|delivery status|mail delivery|automatic reply)", re.I)
NOREPLY = re.compile(r"(no[-_.]?reply|do[-_.]?not[-_.]?reply|mailer-daemon|postmaster|bounce|notifications?@)", re.I)


def is_auto_or_bulk(headers: dict[str, str], subject: str, sender: str) -> bool:
    h = {k.lower(): (v or "") for k, v in headers.items()}
    if h.get("auto-submitted", "no").lower() not in ("", "no"):
        return True
    if "list-unsubscribe" in h or "list-id" in h or h.get("precedence", "").lower() in ("bulk", "junk", "list"):
        return True
    if "x-autoreply" in h or "x-autorespond" in h:
        return True
    return bool(AUTO_SUBJECT.search(subject or "") or NOREPLY.search(parseaddr(sender)[1]))


def sender_authenticated(headers: dict[str, str], sender: str) -> bool:
    """True only if Gmail's Authentication-Results shows DMARC pass, or SPF+DKIM pass, for the From domain."""
    ar = " ".join(v for k, v in headers.items() if k.lower() == "authentication-results").lower()
    if not ar:
        return False
    if "dmarc=pass" in ar:
        return True
    return "spf=pass" in ar and "dkim=pass" in ar
