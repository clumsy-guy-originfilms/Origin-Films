"""Settings. Secrets come from environment variables only; nothing here is secret."""
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
MODEL = "claude-opus-5-5"

# Notion data source IDs of the new structure (not secret).
NOTION_DS = {
    "companies": "c4642b72-dfbc-48a2-a8e5-c0d7de987af7",
    "contacts": "22069fed-5ee7-4ee4-ac72-e0c35d082ff1",
    "deals": "af2e236b-63eb-4bee-a6a5-743889d2a344",
    "projects": "ec17b8da-179c-46ea-8425-8c426f9e7dc4",
    "invoices": "d80aae7a-22e2-4d82-a159-114b263b450c",
    "tasks": "e6a8546b-0ee3-42e4-805e-6934be5d6cb5",
    "knowledge": "02973b29-dd5b-44dd-877b-178f12bf1045",
    "activity_log": "b0c32d67-c8f6-4a19-ac82-ae30dda3ec5f",
}

AGENTS = ("inbound", "chief_of_staff")
SLACK_CHANNELS = {"inbound": "agent-inbound", "chief_of_staff": "agent-chief-of-staff"}

# Senders whose mail duplicates a webhook we already receive.
TYPEFORM_NOTIFICATION_DOMAINS = ("typeform.com", "typeform.io")
OWN_DOMAINS = ("originfilms.ca",)

FOLLOW_UP_BUSINESS_DAYS = (3, 6, 10, 15)
QUIET_START_HOUR, QUIET_END_HOUR = 23, 7


@dataclass(frozen=True)
class Settings:
    owner_slack_user_id: str = field(default_factory=lambda: os.getenv("OWNER_SLACK_USER_ID", ""))
    booking_link: str = field(default_factory=lambda: os.getenv("BOOKING_LINK", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///origin.db"))
    daily_budget_usd: float = field(default_factory=lambda: float(os.getenv("DAILY_BUDGET_USD", "3")))
    max_drafts_per_day: int = field(default_factory=lambda: int(os.getenv("MAX_DRAFTS_PER_DAY", "25")))
    max_drafts_per_recipient_per_day: int = 1
    max_drafts_per_thread: int = 6
