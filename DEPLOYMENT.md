# 🚀 Deployment Guide — Zero Cost Cloud Setup

## Overview
This guide deploys your AI Lead Generator to the cloud for free.
Total setup time: ~30 minutes.

---

## Step 1 — Get Your Free API Keys

### A) Anthropic Claude API
1. Go to https://console.anthropic.com
2. Sign up → go to "API Keys" → Create key
3. Copy the key (starts with `sk-ant-...`)
4. Free credits are given on signup — enough for hundreds of pipeline runs

### B) Supabase (Free Database)
1. Go to https://supabase.com → Sign up
2. Click "New Project" → choose a name like "lead-generator"
3. Pick a region close to you (e.g., eu-west for UAE)
4. After creation, go to: Settings → API
5. Copy:
   - Project URL (looks like: https://xxxx.supabase.co)
   - anon/public key (long string)
6. Go to SQL Editor → New Query → paste contents of `supabase_setup.sql` → Run

### C) Upstash Redis (Free Queue — Optional)
1. Go to https://upstash.com → Sign up
2. Create Database → choose region → Free tier
3. Copy REST URL and REST Token
4. (If you skip this, the app still works — Redis is optional for now)

---

## Step 2 — Push Code to GitHub

```bash
# On your computer or use GitHub web upload
git init
git add .
git commit -m "Initial commit — AI Lead Generator"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/lead-generator.git
git push -u origin main
```

---

## Step 3 — Deploy to Railway (Recommended — Easiest)

1. Go to https://railway.app → Sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `lead-generator` repository
4. Railway auto-detects Python and `railway.toml`
5. Go to your service → "Variables" tab → Add these:

```
ANTHROPIC_API_KEY     = sk-ant-your-key
SUPABASE_URL          = https://xxxx.supabase.co
SUPABASE_KEY          = your-anon-key
UPSTASH_REDIS_REST_URL    = https://your-redis.upstash.io  (optional)
UPSTASH_REDIS_REST_TOKEN  = your-token  (optional)
```

6. Railway deploys automatically
7. Click "Generate Domain" to get your public URL

Your API will be live at: `https://your-app.railway.app`

---

## Alternative: Deploy to Render (Also Free)

1. Go to https://render.com → Sign up with GitHub
2. New → Web Service → Connect your repo
3. Render reads `render.yaml` automatically
4. Add environment variables in the dashboard
5. Deploy

---

## Step 4 — Set Up the Database

In Supabase SQL Editor, run `supabase_setup.sql` (already done in Step 1B).

---

## Step 5 — Test Your Deployment

```bash
# Health check
curl https://your-app.railway.app/health

# Run a lead generation pipeline
curl -X POST https://your-app.railway.app/run \
  -H "Content-Type: application/json" \
  -d '{"query": "Off-plan investors in Dubai with 2M budget", "max_leads": 10}'

# Returns: {"job_id": "abc-123", "status": "started"}

# Check status
curl https://your-app.railway.app/status/abc-123

# Get leads (once done)
curl https://your-app.railway.app/leads?job_id=abc-123
```

---

## Step 6 — Connect Your Frontend Dashboard

In your React dashboard (the artifact), point the API URL to:
```
https://your-app.railway.app
```

---

## Free Tier Limits

| Service     | Free Limit                          | Enough for?              |
|-------------|-------------------------------------|--------------------------|
| Railway     | $5 credit/month (~500hrs)           | Plenty for this app      |
| Render      | 750hrs/month, sleeps after 15min    | Good for testing         |
| Supabase    | 500MB database, 2GB bandwidth       | Thousands of leads       |
| Upstash     | 10,000 commands/day                 | Many pipeline runs       |
| Anthropic   | Free credits on signup              | ~50–100 full pipeline runs|

---

## Tips

- Use **Railway** over Render — it doesn't sleep between requests
- Use **claude-3-5-haiku** (already set in config) — it's the cheapest Claude model
- Each full pipeline run uses approximately 3–5 API calls to Claude
- DuckDuckGo search is completely free with no limits enforced

---

## Troubleshooting

**App not starting?**
- Check Railway logs for Python import errors
- Make sure all environment variables are set

**No leads found?**
- Try a more specific query
- DuckDuckGo may occasionally rate-limit — wait 1 minute and retry

**Supabase errors?**
- Confirm you ran `supabase_setup.sql`
- Check that SUPABASE_URL and SUPABASE_KEY are correct

---

## Telegram Setup (Optional but Highly Recommended)

Dubai has massive real estate investor groups on Telegram with real buying intent.
This is the highest-quality signal source — but requires a one-time local setup.

### Step 1 — Get Telegram API credentials (free)
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click **"API development tools"**
4. Fill in App title: `LeadGen`, Platform: `Other`
5. Copy your **API ID** (number) and **API Hash** (string)

### Step 2 — Join relevant groups
Manually join these public Dubai RE groups in your Telegram app:
- @dubaipropertyinvestors
- @dubai_real_estate_investors
- @offplandubai
- @uaerealestateinvestors
- Any other Dubai RE groups you know

### Step 3 — First-time session (run locally once)
The first login requires entering an OTP sent to your phone.
Do this locally before deploying:

```bash
pip install telethon
python3 -c "
import asyncio
from telethon import TelegramClient
async def login():
    client = TelegramClient('telegram_session', YOUR_API_ID, 'YOUR_API_HASH')
    await client.start(phone='YOUR_PHONE')
    print('Session saved!')
    await client.disconnect()
asyncio.run(login())
"
```

This creates a `telegram_session.session` file.

### Step 4 — Upload session to Railway
In Railway dashboard → your service → **Files** tab:
Upload `telegram_session.session` to `/tmp/telegram_session.session`

Or set it as a base64 environment variable:
```bash
base64 telegram_session.session
# Paste output as TELEGRAM_SESSION_B64 env var
```

### Step 5 — Add to Railway environment variables
```
TELEGRAM_API_ID     = 12345678
TELEGRAM_API_HASH   = abcdef1234567890abcdef
TELEGRAM_PHONE      = +971XXXXXXXXX
```

Once configured, the Telegram scraper automatically activates on every pipeline run.
