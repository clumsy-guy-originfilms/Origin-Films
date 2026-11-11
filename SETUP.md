# Setup guide for Danny

This guide connects the agents to your accounts. There are seven parts, and they should be done in order. Allow about an hour.

**How it works.** Each part ends with one or more secret values, such as a key or a token. You paste each value into one place only: the Variables page of your Railway service. Railway is the server that runs the agents, and it hands the values to them when they start.

**The one safety rule.** Never paste a key or token into Slack, Notion, email, a chat with Claude, or this repository. If you do so by accident, delete that key where you created it and make a new one.

Button names on these websites change from time to time. If a label is slightly different from what is written here, look for the closest match.

---

## Part 1: Create the server on Railway

You do this first so that you have somewhere to paste the values from the later parts.

1. Go to railway.com and sign in with your GitHub account.
2. Click **New Project**, then choose **Deploy from GitHub repo**.
3. Choose the repository named **origin-films**. If it is not listed, click the option to configure GitHub access and allow Railway to see that repository.
4. Railway will start building. The first build will fail or crash. That is expected, because the keys are not in place yet.
5. Inside the project, click **New** (or **Create**), choose **Database**, then choose **PostgreSQL**. This is the small database where the agents keep their audit trail.
6. Click on the **origin-films** service (not the database), then open the **Variables** tab. This is the page you will return to in every part below.
7. On that Variables page, click **New Variable**. Name it `DATABASE_URL`. For the value, choose the reference to the Postgres database's `DATABASE_URL` that Railway offers in the dropdown.
8. Open the service's **Settings** tab, find the **Networking** section, and click **Generate Domain**. Copy the web address it gives you and keep it for Part 5. It looks like `something.up.railway.app`.

**To add a variable in any later part:** open the service, click **Variables**, click **New Variable**, type the name exactly as written in this guide, paste the value, and save.

---

## Part 2: Anthropic key (lets the agents think and write)

1. Go to console.anthropic.com and sign in.
2. Open **Settings**, then **Limits**, and set a monthly spend limit. Start low, for example $25. This protects you if something goes wrong.
3. Open **API keys** and click **Create Key**. Name it "Origin Agents".
4. Copy the key. It is shown only once.
5. In Railway, add a variable named `ANTHROPIC_API_KEY` and paste the key as its value.

---

## Part 3: Slack bot (how the agents talk to you)

**Create the bot**

1. In GitHub, open this repository, open the `slack` folder, and open the file `manifest.yaml`. Click the copy button to copy the whole file.
2. Go to api.slack.com/apps and click **Create New App**.
3. Choose **From a manifest**.
4. Choose the **Origin Films** workspace and click **Next**.
5. Select the **YAML** tab, delete what is in the box, paste what you copied, and click **Next**, then **Create**.
6. Click **Install to Workspace** and then **Allow**.

**Copy three values into Railway**

7. In the left menu, click **OAuth & Permissions**. Copy the **Bot User OAuth Token**, which starts with `xoxb-`. In Railway, add it as `SLACK_BOT_TOKEN`.
8. In the left menu, click **Basic Information**. Scroll to **App-Level Tokens** and click **Generate Token and Scopes**. Name it "socket", click **Add Scope**, choose `connections:write`, and click **Generate**. Copy the token, which starts with `xapp-`. In Railway, add it as `SLACK_APP_TOKEN`.
9. Open Slack itself. Click your own profile picture, click **Profile**, click the three dots, and click **Copy member ID**. It starts with `U`. In Railway, add it as `OWNER_SLACK_USER_ID`. This tells the agents that only your account may pause them or change their mode.

**Let the bot into its channels**

10. Two private channels already exist: `#agent-inbound` and `#agent-chief-of-staff`. Open each one, type `/invite @Origin Agents`, and press Enter.

---

## Part 4: Notion (where the agents keep leads and deals)

1. Go to notion.so/profile/integrations and click **New integration**.
2. Name it "Origin Agents". Choose the **Origin Films** workspace. Choose the type **Internal**. Save.
3. Copy the **Internal Integration Secret**. In Railway, add it as `NOTION_TOKEN`.
4. In Notion, open the page called **Origin OS (new structure, in build)**.
5. Click the three dots at the top right of that page, click **Connections**, and add **Origin Agents**.

Share only that one page. This is what keeps the agents away from your old databases and from the Weddings.IO material.

---

## Part 5: Typeform (so website inquiries reach the agent instantly)

1. Make up a long random phrase to use as a password, for example four unrelated words and some numbers. In Railway, add it as `TYPEFORM_WEBHOOK_SECRET`.
2. In Typeform, open your inquiry form, click **Connect**, then click **Webhooks**, then **Add a webhook**.
3. In the address box, type `https://`, then the Railway web address from Part 1, then `/webhooks/typeform`. For example: `https://something.up.railway.app/webhooks/typeform`.
4. Save it, then click **Edit** on the webhook, turn on the **Secret** option, and paste the same phrase you used in step 1.
5. Switch the webhook **on**.

---

## Part 6: Gmail for booking@originfilms.ca (so the agent can read inquiries and write drafts)

This is the longest part. The agent will be able to read mail, add labels and create drafts. The code has no ability to send.

**Create the Google project**

1. Sign in to Google as **booking@originfilms.ca**. Use a private browser window so you are not signed in as anyone else.
2. Go to console.cloud.google.com. Click the project menu at the top, click **New Project**, name it "Origin Agents", and create it.
3. In the search bar at the top, type **Gmail API**, open it, and click **Enable**.

**Set up the sign-in screen**

4. In the search bar, type **OAuth consent screen** and open it (it may be called **Google Auth Platform**). Click **Get started**.
5. Enter the app name "Origin Agents" and choose booking@originfilms.ca as the support email.
6. For the audience, choose **Internal**. This matters: with Internal, the sign-in does not expire every week.
7. Finish and save.

**Create the credentials**

8. Open **Clients** (or **Credentials**) and click **Create client** (or **Create credentials**, then **OAuth client ID**).
9. For the application type, choose **Web application**. Name it "Origin Agents".
10. Under **Authorized redirect URIs**, click **Add URI** and paste exactly: `https://developers.google.com/oauthplayground`
11. Click **Create**. Copy the **Client ID** and add it in Railway as `GMAIL_CLIENT_ID`. Copy the **Client secret** and add it in Railway as `GMAIL_CLIENT_SECRET`. Keep this window open for the next steps.

**Get the long-lived sign-in token**

12. Go to developers.google.com/oauthplayground.
13. Click the gear icon at the top right. Tick **Use your own OAuth credentials**. Paste the Client ID and Client secret from step 11. Close the panel.
14. On the left, in the box labelled **Input your own scopes**, paste exactly: `https://www.googleapis.com/auth/gmail.modify`
15. Click **Authorize APIs**. Choose booking@originfilms.ca and click **Allow**.
16. Click **Exchange authorization code for tokens**.
17. Copy the **Refresh token**. In Railway, add it as `GMAIL_REFRESH_TOKEN`.

---

## Part 7: Finish and switch on

1. In Railway, add one more variable named `BOOKING_LINK`. Its value is the web address clients use to book a call with you.
2. Check that the Variables page now lists all eleven names:
   `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OWNER_SLACK_USER_ID`, `NOTION_TOKEN`, `TYPEFORM_WEBHOOK_SECRET`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `BOOKING_LINK`.
3. Railway restarts the service by itself after variables change. If it does not, open **Deployments** and click **Redeploy**.
4. In Slack, open a direct message with **Origin Agents** and send the word `status`. It should reply that both agents are in sandbox.

If the bot does not reply, open Railway, click **Deployments**, open the latest one, and copy the last lines of the log to whoever is helping you. Check first that the lines contain no keys.

**What sandbox means.** Every agent starts in sandbox mode. In sandbox, an agent reads incoming inquiries and tells you in Slack what it would have done, but it creates nothing. When you are happy with what you see, send `sandbox off inbound`. From then on it creates Notion records and Gmail drafts. It still cannot send an email; you press Send.

---

## Also do this once: protect GitHub

In GitHub, click your profile picture, open **Settings**, then **Password and authentication**, and turn on **two-factor authentication**.

Requiring approval before changes reach the main branch ("branch protection") needs a paid GitHub plan for a private repository. Until you upgrade, treat it as a house rule: nothing changes in the `vault` folder without your say-so.
