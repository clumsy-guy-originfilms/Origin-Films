# Runbook: what to do when

## 1. Stop everything right now
In Slack, message the Origin Agents bot: `pause all`. To undo: `resume all`.
If Slack or the bot is not responding, stop it from outside:
1. Railway > the project > the service > Settings > remove the deployment (or scale to zero).
2. If you suspect a leak: Google Account for booking@ > Security > Third-party access > remove "Origin Agents"; and delete the API key in the Anthropic Console.

## 2. Check an agent
`status` in Slack shows each agent as paused, sandbox, or live (drafts only).
- Sandbox: reads and reports what it would do. Creates nothing.
- Live (drafts only): creates Notion records and Gmail drafts. It cannot send email.
`sandbox off inbound` and `sandbox on inbound` switch one agent. Only Danny's account can do this.

## 3. An agent has gone quiet or is erroring
1. Railway > Deployments > Logs. Read the last error.
2. "401" or "invalid_grant" for Gmail: the Google sign-in expired. Redo SETUP.md step 5.
3. "budget reached": the daily model budget was hit. It resets at midnight Eastern, or raise DAILY_BUDGET_USD.
4. Otherwise press Redeploy. If it fails again, pause all and ask for help with the log text.

## 4. A lead was missed or mislabelled
Check the Gmail label "Agent/Suspected spam". Reply by hand, then add the case to `attacks/library.yaml` or tell whoever maintains the code.

## 5. Undo something an agent wrote
Every Notion write is recorded with its before and after values in the server's audit table. A one-click revert is not built yet; for now, fix the field in Notion by hand using Notion's page history.

## 6. Before any change goes live
Run the tests, which include the attack library:

    python -m pytest -q
