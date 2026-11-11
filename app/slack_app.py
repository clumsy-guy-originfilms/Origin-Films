"""One Slack app, one bot, one DM. Agents post under their own name in their
own channel. Mode changes are accepted only from the owner's Slack user ID,
which Slack attaches to every event; display names are never trusted.
NOTE: not yet exercised against the live workspace."""
import os
import re

from .config import AGENTS, SLACK_CHANNELS

PERSONA = {"inbound": ("Inbound", ":inbox_tray:"), "chief_of_staff": ("Chief of Staff", ":clipboard:")}
ALIASES = {"inbound": "inbound", "chief": "chief_of_staff", "chief of staff": "chief_of_staff", "cos": "chief_of_staff", "all": "all"}
CMD = re.compile(r"^\s*(pause|resume|sandbox on|sandbox off|status)\s*(.*)$", re.I)


class SlackOut:
    """What agents use to speak. Posting is the only thing it can do."""
    def __init__(self, client, owner_id: str):
        self.client, self.owner_id = client, owner_id

    def alert(self, agent: str, text: str):
        name, icon = PERSONA.get(agent, (agent, ":robot_face:"))
        self.client.chat_postMessage(channel=f"#{SLACK_CHANNELS.get(agent, 'agent-chief-of-staff')}", text=text,
                                     username=name, icon_emoji=icon, unfurl_links=False)


def handle_command(text: str, user_id: str, owner_id: str, store) -> str | None:
    """Pure function so it can be tested. Returns the reply, or None if not a command."""
    m = CMD.match(text or "")
    if not m:
        return None
    verb, target = m.group(1).lower(), ALIASES.get(m.group(2).strip().lower() or "all")
    if verb == "status":
        return "\n".join(f"• {a}: " + ("paused" if store.paused(a) else "sandbox" if store.sandbox(a) else "live (drafts only)") for a in AGENTS)
    if not owner_id or user_id != owner_id:
        return "Only Danny can change agent modes."
    if target is None:
        return "Which agent? Try: pause inbound, resume all, sandbox off inbound, status."
    if verb in ("pause", "resume"):
        keys = ["paused:all"] if target == "all" else [f"paused:{target}"]
        for k in keys:
            store.set(k, "yes" if verb == "pause" else "no")
        store.log("owner", f"mode.{verb}", target)
        return f"{'Paused' if verb == 'pause' else 'Resumed'}: {target}."
    if target == "all":
        return "Sandbox is switched one agent at a time. Example: sandbox off inbound."
    store.set(f"sandbox:{target}", "on" if verb == "sandbox on" else "off")
    store.log("owner", f"mode.{verb}", target)
    return f"Sandbox {'ON' if verb == 'sandbox on' else 'OFF'} for {target}." + ("" if verb == "sandbox on" else " It will now create real Notion records and Gmail drafts. It still cannot send email.")


def build(store, owner_id: str):
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    def respond(event, say):
        if event.get("bot_id") or event.get("subtype"):
            return
        text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
        reply = handle_command(text, event.get("user", ""), owner_id, store)
        say(reply or "I understand: `status`, `pause <agent|all>`, `resume <agent|all>`, `sandbox on|off <agent>`. "
                     "Questions about deals are answered from the Notion views for now.", thread_ts=event.get("ts"))

    app.event("app_mention")(respond)
    app.event("message")(lambda event, say: respond(event, say) if event.get("channel_type") == "im" else None)
    return app, SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
