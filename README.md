# 🏢 AI Real Estate Lead Generator
## Cloud-Ready Multi-Agent Pipeline

### Free Cloud Deployment Stack
- **Backend**: Railway (free tier) or Render (free tier)
- **Database**: Supabase (free tier - PostgreSQL)
- **Cache/Queue**: Upstash Redis (free tier)
- **AI**: Anthropic Claude API (free credits)
- **Scraping**: DuckDuckGo + BeautifulSoup (free, no key needed)
- **Scheduling**: Railway Cron or Render Cron Jobs (free)

### Project Structure
```
leadgen/
├── main.py                  # FastAPI entry point
├── requirements.txt         # Dependencies
├── railway.toml             # Railway deployment config
├── render.yaml              # Render deployment config
├── .env.example             # Environment variables template
├── agents/
│   ├── manager.py           # Manager agent (orchestrator)
│   ├── discovery.py         # Lead Discovery Agent
│   ├── extraction.py        # Data Extraction Agent
│   ├── qualification.py     # Qualification & Scoring Agent
│   ├── contact_finder.py    # Contact Finder Agent
│   └── report_generator.py  # Report Generator Agent
├── core/
│   ├── database.py          # Supabase connection
│   ├── queue.py             # Upstash Redis queue
│   └── models.py            # Data models
├── api/
│   └── routes.py            # API endpoints
└── config/
    └── settings.py          # Configuration
```

### Quick Deploy (Railway - Recommended)
1. Push this code to GitHub
2. Connect repo to Railway.app
3. Add environment variables
4. Deploy — done!

### API Endpoints
- `POST /run` — Start a lead generation pipeline
- `GET /leads` — Get all generated leads
- `GET /leads/{job_id}` — Get leads for specific job
- `GET /status/{job_id}` — Check pipeline status
- `DELETE /leads` — Clear all leads
