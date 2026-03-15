# Quota

An open-source autonomous sales agent framework built on [Claude](https://anthropic.com/claude). Quota runs a team of agents that research prospects, execute email sequences, monitor your inbox, and report on pipeline — all orchestrated by a CRO agent that reads your OKRs and decides what to focus on each day.

**Best experienced in Claude Code.** Drop the repo, set your env vars, prompt your agents, and run.

---

## What you get

| Agent | Runs | What it does |
|-------|------|--------------|
| **CRO** | 7am daily | Reviews OKRs, dispatches sub-agents, posts a daily plan to Slack |
| **Scout** | On demand | Researches companies, finds + verifies contacts via Apollo + FullEnrich |
| **Outreach** | On demand | Executes 3-touch email sequences — Tier 1 via Gmail drafts, Tier 2/3 auto-sends |
| **Enablement** | On demand | Generates call prep briefs from CRM data before meetings |
| **Channels** | On demand | Partner opportunity reports |
| **Inbox** | Every 15min | Reads Gmail, classifies replies, updates CRM |
| **Digest** | 8am daily | Pipeline activity summary posted to Slack |
| **Follow-Up** | 10am daily | Drafts post-response follow-ups, queues Tier 1 for approval |

Everything is editable. Agent prompts live in `prompts/` as Markdown files and are hot-reloadable via the dashboard — no redeploy needed.

---

## Before you start

Set up these accounts first. Do this before touching the code — you'll need the credentials in your `.env` and some require browser-based flows.

| Service | Required | What for | Get it |
|---------|----------|----------|--------|
| **Anthropic** | Yes | All agent reasoning | [console.anthropic.com](https://console.anthropic.com) |
| **PostgreSQL** | Yes | Agent configs, OKRs, run history | Railway (easiest), Supabase, or local Docker |
| **Attio** | Yes | CRM — accounts, contacts, pipeline state | [attio.com](https://attio.com) |
| **Google Cloud** | Yes | Gmail OAuth2 — send + draft + read email | [console.cloud.google.com](https://console.cloud.google.com) |
| **Slack** | Recommended | Approval cards, notifications, @bot | [api.slack.com/apps](https://api.slack.com/apps) |
| **Apollo.io** | Optional | Contact discovery (Scout is disabled without it) | [apollo.io](https://app.apollo.io) |
| **FullEnrich** | Optional | Email verification waterfall | [fullenrich.com](https://fullenrich.com) |

> **Graceful degradation:** The server starts and all agents run even if optional integrations are missing. Agents that need a missing integration will skip those steps and log a warning.

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-org/quota.git
cd quota
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Set up PostgreSQL

**Local (Docker):**
```bash
docker run -d --name quota-db \
  -e POSTGRES_DB=quota \
  -e POSTGRES_USER=quota \
  -e POSTGRES_PASSWORD=quota \
  -p 5432:5432 postgres:16

# Use this as your DATABASE_URL:
# postgresql+asyncpg://quota:quota@localhost:5432/quota
```

**Railway:** Add a PostgreSQL plugin to your project. Copy the connection string from Railway → Variables → `DATABASE_URL`. Change the scheme from `postgresql://` to `postgresql+asyncpg://` — this is required, asyncpg won't connect without it.

### 3. Set up Gmail OAuth2

Gmail is used for three things: sending email (REST API via OAuth2), creating drafts (REST API via OAuth2), and reading the inbox (IMAP via App Password). These use two different auth mechanisms.

**Part A — OAuth2 for sending and drafts:**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → create a new project (or use an existing one)
2. APIs & Services → Library → search "Gmail API" → Enable
3. APIs & Services → Credentials → Create Credentials → **OAuth client ID**
   - Application type: **Desktop app**
   - Name anything (e.g. "Quota")
4. Download the credentials JSON → save as `credentials.json` in the project root
5. Run the OAuth setup script:
   ```bash
   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
   python oauth_setup.py
   ```
   A browser window opens — authorize with the Gmail account you want to send from. The script creates `gmail_token.json` and prints the connected address.
6. Extract your values from `credentials.json` and `gmail_token.json`:
   ```bash
   # From credentials.json → "installed" → "client_id" and "client_secret"
   # From gmail_token.json → "refresh_token"
   cat credentials.json | python3 -c "import sys,json; d=json.load(sys.stdin)['installed']; print('CLIENT_ID:', d['client_id']); print('CLIENT_SECRET:', d['client_secret'])"
   cat gmail_token.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('REFRESH_TOKEN:', d['refresh_token'])"
   ```
7. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` in your `.env`

> **Do not commit `credentials.json` or `gmail_token.json`** — they are in `.gitignore` but double-check before pushing.

**Part B — App Password for inbox monitoring (IMAP):**

IMAP uses a separate Gmail App Password, not OAuth2.

1. Go to your Google Account → Security → 2-Step Verification (must be enabled)
2. Search "App passwords" → create one → name it "Quota IMAP"
3. Copy the 16-character password → set as `GMAIL_APP_PASSWORD` in `.env`

> If you skip this, the Inbox agent won't run. The other agents (Outreach, Scout, etc.) are unaffected.

### 4. Set up Attio

Attio is the CRM — the shared state all agents read from and write to. Two things to configure:

**Custom fields:** Quota expects specific field slugs on your Attio objects. Create these in Attio → Settings → Objects before running agents:

*Companies object — required fields:*
| Field name | Slug | Type |
|------------|------|------|
| Outreach Status | `outreach_status` | Select |
| Account Tier | `account_tier` | Number |
| Current Touch | `current_touch` | Number |
| Last Touch Date | `last_touch_date` | Date |
| Next Touch Date | `next_touch_date` | Date |
| Channel Partner | `channel_partner` | Select |

*People object — required fields:*
| Field name | Slug | Type |
|------------|------|------|
| Sequence Status | `sequence_status` | Select |
| Sequence Touch | `sequence_touch` | Number |
| Sequence Function | `sequence_function` | Select |
| Last Touch Date | `last_touch_date` | Date |
| Next Touch Date | `next_touch_date` | Date |

> If your Attio workspace already has fields with different slugs, update `_SELECT_SLUGS` in `src/tools/attio_tools.py` and the tool descriptions so agents know the right names.

**Tiered account lists:** Create three Attio lists named `Tier 1`, `Tier 2`, `Tier 3`. Scout reads these to know which accounts to prioritize. Add your target accounts to the appropriate list.

**API key:** Attio → Settings → API Keys → create a key → set as `ATTIO_API_KEY`.

### 5. Set up Slack

Three separate steps in the Slack app config — all required for the full approval flow and @bot:

**Step 1 — Create the app:**
1. [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch
2. Name it (e.g. "Quota") and pick your workspace

**Step 2 — Bot permissions** (OAuth & Permissions → Bot Token Scopes):
- `chat:write` — post messages
- `chat:write.public` — post to channels without joining
- `channels:read` — read channel info
- `im:write` and `im:history` — DM support

Install the app → copy the **Bot User OAuth Token** (`xoxb-...`) → set as `SLACK_BOT_TOKEN`.

**Step 3 — Events API** (for the @CRO conversational bot):
1. Event Subscriptions → Enable Events
2. Request URL: `https://your-deployed-url/webhooks/slack/events`
   - Slack will send a challenge request — your server must be running and reachable
3. Subscribe to bot events: `app_mention`, `message.im`

**Step 4 — Interactive Components** (for approval card buttons):
1. Interactivity & Shortcuts → turn on Interactivity
2. Request URL: `https://your-deployed-url/webhooks/slack`

**Signing secret:** Basic Information → Signing Secret → copy → set as `SLACK_SIGNING_SECRET`. This is how the server verifies that webhook payloads actually came from Slack.

**Channel ID:** Right-click the approval channel in Slack → Copy link → the last segment is the channel ID (e.g. `C08XXXXXXXX`) → set as `SLACK_APPROVAL_CHANNEL`.

> You can skip Slack entirely for local dev. Agents still run — they just won't post notifications or approval cards.

### 6. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in every value. The required ones to get started:

```env
ANTHROPIC_API_KEY=...
DATABASE_URL=postgresql+asyncpg://...
ATTIO_API_KEY=...
GMAIL_FROM_EMAIL=you@yourdomain.com
GMAIL_FROM_NAME=Your Name
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
GMAIL_APP_PASSWORD=...         # 16-char App Password for IMAP
DASHBOARD_PASSWORD=...         # Change this — it protects the management UI
JWT_SECRET=...                 # Run: openssl rand -hex 32
```

### 7. Customize your prompts

**This is the most important step.** Agents do nothing useful until their prompts describe your business.

Start with `prompts/shared.md` — this is prepended to every agent's context. Fill in your company, product, ICP, and any rules that apply across all agents.

For each agent prompt, you can either:
- **Fill in the placeholders manually** — replace every `[YOUR X]` with your context
- **Use Claude to generate it** — each `prompts/*.md` file includes a ready-to-copy Claude prompt that generates a complete system prompt when you describe your business. Open [claude.ai](https://claude.ai), paste the generator prompt, describe your use case, and paste the output back into the file

> In Claude Code, you can say: *"Read prompts/shared.md and help me fill it in for [my company]. We sell [X] to [Y]."* Claude Code has full file access and will do it interactively.

### 8. Update email signature

Open `src/tools/email_tools.py` and find `_SIGNATURE_HTML`. Replace the placeholder with your actual signature — name, title, company, phone, calendar link. This appears at the bottom of every outreach email.

### 9. Run locally

```bash
uvicorn src.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) — sign in with your `DASHBOARD_PASSWORD`. You should see all 8 agents listed with status "never run".

**Trigger a test run:**
```bash
# Get a JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-dashboard-password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Run the inbox agent (safe — read-only)
curl -X POST http://localhost:8000/agents/inbox/heartbeat \
  -H "Authorization: Bearer $TOKEN"
```

Check the Runs page in the dashboard to see what happened.

---

## Deploy to Railway

```bash
# Push your repo to GitHub, then:
```

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Add a PostgreSQL plugin (Railway → your project → New → Database → Add PostgreSQL)
3. Copy `DATABASE_URL` from Railway → Variables, change `postgresql://` → `postgresql+asyncpg://`, paste it back
4. Add all your env vars from `.env` into Railway → Variables
5. Deploy — Railway auto-detects the Dockerfile

**After first deploy:**
- The app seeds the database from your `prompts/*.md` files on startup
- Once seeded, editing prompts in the dashboard overwrites the DB record — the `.md` files are only read on first run per agent

**Slack webhook URLs:** Once deployed, go back to your Slack app config and set the Events API and Interactive Components URLs to your Railway domain.

---

## Using Claude Code

With the repo open in Claude Code, you can:

**Customize prompts conversationally:**
> *"Read all the files in prompts/ and help me rewrite shared.md for a B2B SaaS company selling to engineering teams at Series B startups."*

**Debug agent behavior:**
> *"The Inbox agent ran but didn't classify this reply correctly. Read src/agents/inbox.py and prompts/inbox.md and tell me why."*

**Extend the system:**
> *"Add a new agent called 'LinkedIn' that drafts LinkedIn connection request messages. Follow the same pattern as outreach.py."*

**Diagnose issues:**
> *"The last CRO run shows 47 turns and took 8 minutes. Read src/agents/cro.py and prompts/cro.md and tell me what's causing it to take so long."*

---

## How prompts work

```
prompts/shared.md  ← prepended to every agent (company context, rules, tone)
       +
prompts/cro.md     ← agent-specific behavior
       =
Full system prompt sent to Claude at each heartbeat
```

Prompts are seeded into the database on first run. After that, the database version is used — editing the `.md` file has no effect until you clear the agent record or use the dashboard editor.

**The fastest path to a working system:**
1. Fill in `shared.md` with your company, product, ICP, rep name, calendar link
2. Keep agent-specific prompts minimal at first — the shared context does most of the work
3. Observe the first few runs on the Runs page
4. Iterate on individual agent prompts based on what you see

---

## Customization

### Add an agent

1. Create `src/agents/your_agent.py` extending `BaseAgent` — implement `async def run(focus=None) -> dict`
2. Add a prompt at `prompts/your_agent.md`
3. Register a heartbeat endpoint in `src/routers/heartbeats.py`
4. Add to `_AGENT_DEFAULTS` in `src/main.py` so it gets seeded
5. Add to `_VALID_AGENTS` in `src/tools/dispatch_tools.py` if the CRO should be able to dispatch it

### Swap the CRM

All CRM logic is in `src/tools/attio_tools.py`. Replace it with HubSpot, Salesforce, or any other CRM. The tool names (e.g. `attio_query_companies`, `attio_update_company`) are referenced in agent prompts — update those too.

### Change models per agent

Each agent has a configurable model in the database, editable in the dashboard without a redeploy. Haiku for fast classification tasks (Inbox, Digest), Sonnet for reasoning and writing (CRO, Scout, Outreach).

---

## Cost ballpark

Running 100 target accounts through a full sequence (monthly):

| Service | Approx cost |
|---------|-------------|
| Claude API (Sonnet + Haiku mix) | $15–40/month |
| Apollo.io (contact sourcing) | $49+/month (or credits) |
| FullEnrich | $20–50/month depending on volume |
| Railway (app + Postgres) | $5–10/month |
| Gmail / Slack / Attio | Per your existing plans |

Token spend is visible per-run in the dashboard. Set `email_daily_send_limit` and `*_batch_size` in `.env` to control pace and cost.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).
