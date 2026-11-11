# Origin Films agent ecosystem: Phase 1

One small always-on server running two agents on a shared core, plus the knowledge vault.

- **Inbound** reads booking@originfilms.ca and Typeform, logs leads in Notion, scores them, and puts replies in Gmail drafts.
- **Chief of Staff** sends the 8 a.m. digest, watches for stalled deals and quiet agents.
- **Safety:** drafts only (no send path exists), one gate for every outbound action, sandbox by default, owner-only controls, duplicate protection, daily caps, and an attack library that runs with the tests.

| Path | What it is |
|---|---|
| `app/` | Shared core and the two agents |
| `app/safety/` | The gate and the screens. Change with care. |
| `attacks/library.yaml` | Fake injection attempts, run on every test |
| `slack/manifest.yaml` | Paste into Slack to create the bot |
| `vault/` | Knowledge vault; open in Obsidian |
| `SETUP.md` | The steps only Danny can do |
| `RUNBOOK.md` | Pause, check, fix |

## Status
Tested offline with stand-ins for Notion, Gmail, Slack and the model: `python -m pytest -q`.
**Not yet run against the live accounts.** The Notion, Gmail and Slack clients were written without credentials, so expect fixes on first deploy; that is what sandbox mode is for.

## Not built yet
Free-form questions in Slack, Fathom and booking-link triggers, one-click revert, team permissions, Agent Activity Log rows in Notion (the audit trail is in the server database for now), and the data migration from the old Notion databases.
