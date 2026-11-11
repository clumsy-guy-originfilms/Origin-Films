"""The single choke point for anything that leaves the building.
Phase 1 has exactly one outbound action: create a Gmail DRAFT in reply to the
person who wrote in. There is no send function anywhere in this codebase;
Danny pressing Send in Gmail is the approval. The gate fails closed."""
from dataclasses import dataclass, field

from ..config import Settings
from ..store import Store
from .screen import outgoing_violations


@dataclass
class Decision:
    allowed: bool
    sandbox: bool = False
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)     # shown to Danny beside the draft


class Gate:
    def __init__(self, store: Store, settings: Settings):
        self.store, self.s = store, settings

    def check_draft(self, *, agent: str, recipient: str, inbound_sender: str, thread: str, body: str,
                    day: str, do_not_contact: bool = False, recipient_verified: bool = True) -> Decision:
        try:
            d = Decision(allowed=True)
            if self.store.paused(agent):
                return Decision(False, reasons=[f"{agent} is paused"])
            if not recipient or recipient.strip().lower() != (inbound_sender or "").strip().lower():
                return Decision(False, reasons=["recipient is not the person who wrote in"])
            if do_not_contact:
                return Decision(False, reasons=["contact is marked do not contact"])
            c = self.store.draft_counts(day, recipient, thread)
            if c["day"] >= self.s.max_drafts_per_day:
                return Decision(False, reasons=["daily draft cap reached"])
            if c["recipient"] >= self.s.max_drafts_per_recipient_per_day:
                return Decision(False, reasons=["already drafted to this address today"])
            if c["thread"] >= self.s.max_drafts_per_thread:
                return Decision(False, reasons=["thread draft cap reached (possible loop)"])
            d.flags += outgoing_violations(body, allowed_links=(self.s.booking_link,))
            if not recipient_verified:
                d.flags.append("address is unverified (typed into a form or failed sender checks): confirm before sending")
            d.sandbox = self.store.sandbox(agent)
            return d
        except Exception as e:                      # any doubt means no
            return Decision(False, reasons=[f"gate error: {e!r}"])
