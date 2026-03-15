# Quota — Claude Code Setup Guide

You are helping someone set up and run the Quota autonomous sales agent framework. This file tells you exactly how to do that.

When someone opens this repo for the first time, **start by running the setup check below** to understand where they are. Then guide them through what's missing — one step at a time, in order.

---

## First thing to do

Run this triage to understand their current state:

```bash
# Check .env exists and what's filled in
cat .env 2>/dev/null || echo "NO .ENV FILE"
```

Then check:
- Is there a `.env` file? If not, create one from `.env.example` before anything else.
- Which variables are empty? That tells you exactly what to set up next.
- Is there a running database? (`DATABASE_URL` set and reachable)

Ask the user: **"What have you already set up? Let me check your .env and tell you what's missing."**

---

## Setup order (follow this sequence — later steps depend on earlier ones)

### Step 1 — Anthropic API key
**Blocks everything.** No agents run without this.

- Get it from: https://console.anthropic.com → API Keys
- Set `ANTHROPIC_API_KEY` in `.env`
- Verify: `python3 -c "import anthropic; c = anthropic.Anthropic(api_key='KEY'); print('ok')"` (replace KEY)

### Step 2 — PostgreSQL database
**Blocks the dashboard and all agents.**

**Local (fastest for testing):**
```bash
docker run -d --name quota-db \
  -e POSTGRES_DB=quota \
  -e POSTGRES_USER=quota \
  -e POSTGRES_PASSWORD=quota \
  -p 5432:5432 postgres:16
```
Set `DATABASE_URL=postgresql+asyncpg://quota:quota@localhost:5432/quota`

**Railway (for production):**
- Railway project → New → Database → Add PostgreSQL
- Copy the DATABASE_URL Railway provides
- **Critical:** change `postgresql://` → `postgresql+asyncpg://` in the URL before saving

Verify the server starts: `uvicorn src.main:app --reload` — look for "Database ready" in the logs.

### Step 3 — Attio CRM
**Blocks all agents from reading or writing pipeline data.**

1. Get API key: Attio → Settings → API Keys → create key → set `ATTIO_API_KEY`
2. **Create custom fields** — this is the most commonly missed step. Agents will fail silently without these.

Run this check to see if the user's Attio has the right fields:
```bash
curl -s "https://api.attio.com/v2/objects/companies/attributes" \
  -H "Authorization: Bearer $ATTIO_API_KEY" | python3 -m json.tool | grep '"slug"' | head -20
```

Required field slugs on **Companies**:
- `outreach_status` (Select) — pipeline stage
- `account_tier` (Number) — 1, 2, or 3
- `current_touch` (Number)
- `last_touch_date` (Date)
- `next_touch_date` (Date)
- `channel_partner` (Select)

Required field slugs on **People**:
- `sequence_status` (Select)
- `sequence_touch` (Number)
- `sequence_function` (Select)
- `last_touch_date` (Date)
- `next_touch_date` (Date)

If fields are missing: Attio → Settings → Objects → [Companies or People] → Attributes → Add attribute. The slug must match exactly.

3. Create three Attio Lists: `Tier 1`, `Tier 2`, `Tier 3`. Scout reads these to find target accounts.

### Step 4 — Gmail (two separate auth mechanisms)

**Part A: OAuth2 for sending emails and creating drafts**

This requires a Google Cloud project. Walk the user through:

1. Go to https://console.cloud.google.com → create or select a project
2. APIs & Services → Library → "Gmail API" → Enable
3. APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON → save as `credentials.json` in the project root
4. Run setup:
   ```bash
   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
   python oauth_setup.py
   ```
   A browser opens — have the user authorize with the Gmail account they want to send from.
5. Extract the values:
   ```bash
   python3 -c "
   import json
   creds = json.load(open('credentials.json'))['installed']
   token = json.load(open('gmail_token.json'))
   print('GOOGLE_CLIENT_ID=' + creds['client_id'])
   print('GOOGLE_CLIENT_SECRET=' + creds['client_secret'])
   print('GMAIL_REFRESH_TOKEN=' + token['refresh_token'])
   "
   ```
6. Set those three values + `GMAIL_FROM_EMAIL` and `GMAIL_FROM_NAME` in `.env`

**Part B: App Password for IMAP inbox monitoring**

This is separate from OAuth2. Without it, the Inbox agent won't run.

1. Google Account → Security → 2-Step Verification must be ON
2. Search "App passwords" → create one (name it "Quota IMAP") → copy the 16-char password
3. Set `GMAIL_APP_PASSWORD` in `.env`

Common error: "Application-specific password required" — this means 2-step verification isn't enabled.

### Step 5 — Slack (three config steps, all needed for full functionality)

**Step 5a — Create the app and get the bot token:**
1. https://api.slack.com/apps → Create New App → From scratch
2. OAuth & Permissions → Bot Token Scopes → add: `chat:write`, `chat:write.public`, `channels:read`, `im:write`, `im:history`
3. Install to workspace → copy Bot User OAuth Token (`xoxb-...`) → set as `SLACK_BOT_TOKEN`
4. Basic Information → Signing Secret → set as `SLACK_SIGNING_SECRET`
5. Right-click the approval channel in Slack → Copy link → last segment is the channel ID → set as `SLACK_APPROVAL_CHANNEL`

**Step 5b — Events API (needed for @CRO bot):**
Must be done after deploying (needs a public URL):
- Event Subscriptions → Enable → Request URL: `https://YOUR-DOMAIN/webhooks/slack/events`
- Subscribe to bot events: `app_mention`, `message.im`

**Step 5c — Interactive Components (needed for approval card buttons):**
Must be done after deploying:
- Interactivity & Shortcuts → Enable → Request URL: `https://YOUR-DOMAIN/webhooks/slack`

Note: Steps 5b and 5c require a deployed server with a public URL. They can be skipped for local testing — agents will still run, they just won't post to Slack.

### Step 6 — Optional: Apollo and FullEnrich

- Apollo: https://app.apollo.io → Settings → API → create key → `APOLLO_API_KEY`
  Without this, Scout won't source new contacts (existing Attio contacts still get sequenced).
- FullEnrich: https://fullenrich.com → Settings → `FULLENRICH_API_KEY`
  Without this, Scout uses Apollo's native email field (lower coverage, more bounces).

### Step 7 — Dashboard credentials

```bash
# Generate a secure JWT secret:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set `JWT_SECRET` (the above output) and `DASHBOARD_PASSWORD` (choose anything) in `.env`.

### Step 8 — Customize agent prompts (most important step)

**Do this before running agents** — agents are useless until the prompts describe the user's business.

Read the current state of the prompts:
```bash
cat prompts/shared.md
```

The `shared.md` file is prepended to every agent. It should describe:
- Company name and what they sell
- Who they sell to (ICP)
- Rep name, email, calendar link
- Tone and rules

**Offer to help write it interactively.** Ask:
> "Tell me about your company — what do you sell, who buys it, and what's your ICP? I'll write your shared.md and all the agent prompts."

Once you have that information, read each prompt file and fill it in properly. The key files to customize first:
1. `prompts/shared.md` — company context, rules, rep info (affects all agents)
2. `prompts/outreach.md` — email sequence angles, CTAs, tone
3. `prompts/scout.md` — ICP criteria, what to look for in target accounts
4. `prompts/cro.md` — orchestration priorities, what to focus on daily

### Step 9 — Email signature

```bash
grep -n "_SIGNATURE_HTML" src/tools/email_tools.py
```

Find `_SIGNATURE_HTML` and help the user update it with their real name, title, company, phone, and calendar link. This appears at the bottom of every outreach email.

### Step 10 — Start the server and test

```bash
uvicorn src.main:app --reload
```

Watch the startup logs for:
- `✓ Database ready` — DB connected
- `✓ Gmail API email client initialized` — sending works
- `✓ Gmail IMAP inbox client initialized` — inbox monitoring works
- `✓ Attio client initialized` — CRM connected
- `✓ Slack client initialized` — notifications work
- Any `WARNING: ... not set` lines tell you what's disabled

**Test a safe first run** (read-only, won't send anything):
```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$(grep DASHBOARD_PASSWORD .env | cut -d= -f2)\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token','ERROR'))")

echo "Token: $TOKEN"

# Run inbox agent (read-only — just checks Gmail, classifies, updates Attio)
curl -X POST http://localhost:8000/agents/inbox/heartbeat \
  -H "Authorization: Bearer $TOKEN"
```

Open http://localhost:8000 — sign in — check the Runs page to see what happened.

---

## Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `asyncpg: password authentication failed` | Wrong DATABASE_URL | Check the URL scheme is `postgresql+asyncpg://` and credentials match |
| `Gmail API: invalid_grant` | Expired or wrong refresh token | Re-run `python oauth_setup.py` |
| `AttioClient: 404 on attribute` | Missing custom field in Attio | Create the field in Attio → Settings → Objects → Attributes |
| `Slack: not_in_channel` | Bot not added to the approval channel | In Slack, type `/invite @YourBotName` in the channel |
| `Slack signature verification failed` | Wrong signing secret | Re-copy from Slack App → Basic Information → Signing Secret |
| Server starts but no agents listed in dashboard | DB not seeded | Check `prompts/` files exist — they seed on first startup |
| `Module not found` errors | Dependencies not installed | Run `pip install -e ".[dev]"` |
| Agent runs 0 times, no errors | Agent disabled | Dashboard → Agents → check the enabled toggle |

---

## Deploying to Railway

1. Push the repo to GitHub
2. Railway → New Project → Deploy from GitHub repo → select the repo
3. Add PostgreSQL: Railway project → New → Database → Add PostgreSQL
4. Set all env vars from `.env` in Railway → Variables
5. **Fix the DATABASE_URL scheme:** Railway gives `postgresql://` — change to `postgresql+asyncpg://`
6. Deploy — Railway auto-detects the Dockerfile

After deploy:
- Go back to Slack app config → add the Railway URL to Events API and Interactive Components
- Check Railway logs for any startup errors

---

## How to extend the system

**Add a new agent:**
```bash
# Show the pattern
cat src/agents/followup.py
```
1. Create `src/agents/your_agent.py` — copy the pattern from `followup.py`
2. Add `prompts/your_agent.md`
3. Register in `src/routers/heartbeats.py` (copy an existing heartbeat endpoint)
4. Add to `_AGENT_DEFAULTS` in `src/main.py`
5. Optionally add to `_VALID_AGENTS` in `src/tools/dispatch_tools.py` so CRO can dispatch it

**Swap the CRM:**
All CRM logic is in `src/tools/attio_tools.py`. The tool names used in prompts (`attio_query_companies`, `attio_update_company`, etc.) are what agents see — if you rename them, update the prompts too.

**Change a model:**
Dashboard → Agents → click the agent → Model dropdown → save. Takes effect at next run. No redeploy needed.

---

## Prompt seeding behavior (important)

Prompts in `prompts/` are read **once** per agent on first startup. After that, the database record is the source of truth.

This means:
- Editing a `.md` file after first run has **no effect** — edit via the dashboard instead
- To force a re-seed: delete the agent record from the DB and restart the server
- The dashboard prompt editor writes to the DB directly — use that for ongoing edits

---

## Quick reference: what each env var does

```
ANTHROPIC_API_KEY      → Claude API — all agent reasoning
DATABASE_URL           → PostgreSQL — must use postgresql+asyncpg:// scheme
ATTIO_API_KEY          → Attio CRM read/write
GMAIL_FROM_EMAIL       → Sender address for all outreach
GMAIL_FROM_NAME        → Sender display name
GOOGLE_CLIENT_ID       → OAuth2 client from Google Cloud Console
GOOGLE_CLIENT_SECRET   → OAuth2 secret from Google Cloud Console
GMAIL_REFRESH_TOKEN    → From oauth_setup.py — for sending + drafts
GMAIL_APP_PASSWORD     → 16-char App Password — for IMAP inbox only
SLACK_BOT_TOKEN        → xoxb-... for posting messages
SLACK_SIGNING_SECRET   → For verifying Slack webhook authenticity
SLACK_APPROVAL_CHANNEL → Channel ID for approvals and notifications
DASHBOARD_PASSWORD     → Login password for the web UI
JWT_SECRET             → run: python3 -c "import secrets; print(secrets.token_hex(32))"
APOLLO_API_KEY         → Optional: contact sourcing via Apollo
FULLENRICH_API_KEY     → Optional: email verification waterfall
```
