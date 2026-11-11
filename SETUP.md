# Setup: the steps only Danny can do

Each step gives you a value to paste into Railway > your service > Variables. Never paste a key into Slack, Notion, email or this repo.

1. **Anthropic API key.** console.anthropic.com > API keys > Create. Then Settings > Limits: set a monthly spend limit. Variable: `ANTHROPIC_API_KEY`.
2. **Slack app.** api.slack.com/apps > Create New App > From a manifest > pick the Origin Films workspace > paste `slack/manifest.yaml`. Install to workspace.
   - OAuth & Permissions > Bot User OAuth Token (starts `xoxb-`) > `SLACK_BOT_TOKEN`
   - Basic Information > App-Level Tokens > Generate with scope `connections:write` (starts `xapp-`) > `SLACK_APP_TOKEN`
   - Your Slack profile > ... > Copy member ID (starts `U`) > `OWNER_SLACK_USER_ID`
   - Create channels `#agent-inbound` and `#agent-chief-of-staff` and run `/invite @Origin Agents` in each.
3. **Notion integration.** notion.so/profile/integrations > New internal integration, workspace Origin Films. Copy the secret > `NOTION_TOKEN`. Then open the page "Origin OS (new structure, in build)" > ... > Connections > add the integration. Share only that page, so the agents cannot see the old databases or Weddings.IO.
4. **Typeform webhook.** Form > Connect > Webhooks > add `https://<your-railway-domain>/webhooks/typeform`, set a secret (any long random text) > `TYPEFORM_WEBHOOK_SECRET`.
5. **Gmail for booking@originfilms.ca.** In Google Cloud Console create a project, enable the Gmail API, set the OAuth consent screen to **Internal**, and create an OAuth client (Desktop). `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and a refresh token obtained while signed in as booking@ > `GMAIL_REFRESH_TOKEN`. This step is the fiddliest; ask for a walkthrough when you get here.
6. **Railway.** New Project > Deploy from GitHub repo > this repo. Add a Postgres database (sets `DATABASE_URL`). Add `BOOKING_LINK`. Generate a domain under Settings > Networking.
7. **GitHub.** Turn on two-factor login. Branch protection for a private repo needs a paid GitHub plan; until then, changes are reviewed by convention.

Every agent starts in sandbox mode. Nothing is created until you send `sandbox off inbound`.
