"""
Simple mobile-friendly dashboard
Access at /dashboard — no coding needed
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from core.database import get_leads, get_job
import json

dashboard_router = APIRouter()

@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    leads = await get_leads()
    
    leads_json = json.dumps(leads)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lead Generator</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, sans-serif; background: #0f0f0f; color: #fff; padding: 16px; }}
h1 {{ font-size: 20px; margin-bottom: 4px; color: #fff; }}
.subtitle {{ color: #888; font-size: 13px; margin-bottom: 20px; }}
.run-btn {{ 
    display: block; width: 100%; padding: 14px;
    background: #7c3aed; color: white; border: none;
    border-radius: 10px; font-size: 16px; font-weight: 600;
    margin-bottom: 12px; cursor: pointer;
}}
.run-btn:disabled {{ background: #444; }}
.query-input {{
    width: 100%; padding: 12px; background: #1a1a1a;
    border: 1px solid #333; border-radius: 10px;
    color: #fff; font-size: 14px; margin-bottom: 12px;
}}
.status-bar {{
    background: #1a1a1a; border-radius: 10px;
    padding: 12px; margin-bottom: 20px;
    font-size: 13px; color: #888; display: none;
}}
.status-bar.active {{ display: block; color: #7c3aed; }}
.status-bar.done {{ color: #22c55e; }}
.status-bar.error {{ color: #ef4444; }}
.stats {{ display: flex; gap: 10px; margin-bottom: 20px; }}
.stat {{ flex: 1; background: #1a1a1a; border-radius: 10px; padding: 12px; text-align: center; }}
.stat-num {{ font-size: 28px; font-weight: 700; color: #7c3aed; }}
.stat-label {{ font-size: 11px; color: #888; margin-top: 4px; }}
.lead-card {{
    background: #1a1a1a; border-radius: 12px;
    padding: 14px; margin-bottom: 12px;
    border-left: 3px solid #7c3aed;
}}
.lead-card.high {{ border-left-color: #22c55e; }}
.lead-card.med {{ border-left-color: #f59e0b; }}
.lead-name {{ font-size: 16px; font-weight: 600; margin-bottom: 6px; }}
.lead-score {{ 
    display: inline-block; padding: 2px 8px;
    border-radius: 20px; font-size: 12px; font-weight: 600;
    background: #7c3aed22; color: #a78bfa; margin-bottom: 8px;
}}
.lead-score.high {{ background: #22c55e22; color: #4ade80; }}
.lead-score.med {{ background: #f59e0b22; color: #fbbf24; }}
.lead-detail {{ font-size: 13px; color: #888; margin: 3px 0; }}
.lead-detail span {{ color: #ccc; }}
.lead-signal {{ 
    font-size: 12px; color: #666; margin-top: 8px;
    padding-top: 8px; border-top: 1px solid #2a2a2a;
    font-style: italic;
}}
.contact-row {{ display: flex; gap: 8px; margin-top: 10px; }}
.contact-btn {{
    flex: 1; padding: 8px; border-radius: 8px; border: none;
    font-size: 13px; font-weight: 500; cursor: pointer; text-align: center;
    text-decoration: none; display: block;
}}
.btn-call {{ background: #22c55e22; color: #4ade80; }}
.btn-wa {{ background: #25d36622; color: #25d366; }}
.btn-li {{ background: #0a66c222; color: #0a66c2; }}
.btn-email {{ background: #7c3aed22; color: #a78bfa; }}
.empty {{ text-align: center; padding: 40px 20px; color: #555; }}
.section-title {{ font-size: 13px; color: #555; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }}
</style>
</head>
<body>

<h1>🏙️ Lead Generator</h1>
<p class="subtitle">Dubai Real Estate Investor Pipeline</p>

<input class="query-input" id="queryInput" 
    placeholder="e.g. investors in Dubai with 2M budget" 
    value="investors in Dubai with 2M budget">

<button class="run-btn" id="runBtn" onclick="runPipeline()">
    🚀 Find New Leads
</button>

<div class="status-bar" id="statusBar">Starting pipeline...</div>

<div class="stats">
    <div class="stat">
        <div class="stat-num" id="totalCount">0</div>
        <div class="stat-label">Total Leads</div>
    </div>
    <div class="stat">
        <div class="stat-num" id="highCount">0</div>
        <div class="stat-label">High Priority</div>
    </div>
    <div class="stat">
        <div class="stat-num" id="contactCount">0</div>
        <div class="stat-label">With Contact</div>
    </div>
</div>

<div class="section-title">Latest Leads</div>
<div id="leadsContainer"></div>

<script>
const allLeads = {leads_json};
let pollingInterval = null;
let currentJobId = null;

function renderLeads(leads) {{
    const container = document.getElementById('leadsContainer');
    
    if (!leads || leads.length === 0) {{
        container.innerHTML = '<div class="empty">No leads yet.<br>Tap "Find New Leads" to start.</div>';
        return;
    }}
    
    // Update stats
    document.getElementById('totalCount').textContent = leads.length;
    document.getElementById('highCount').textContent = leads.filter(l => l.score >= 70).length;
    document.getElementById('contactCount').textContent = leads.filter(l => l.phone || l.email).length;
    
    container.innerHTML = leads.slice(0, 30).map(lead => {{
        const scoreClass = lead.score >= 80 ? 'high' : lead.score >= 60 ? 'med' : '';
        const scoreLabel = lead.score >= 80 ? 'HIGH PRIORITY' : lead.score >= 60 ? 'MEDIUM' : 'NURTURE';
        
        const phone = lead.phone || '';
        const waNum = phone.replace(/[^0-9+]/g, '');
        
        let contactBtns = '';
        if (phone) {{
            contactBtns += `<a class="contact-btn btn-call" href="tel:${{phone}}">📞 Call</a>`;
            contactBtns += `<a class="contact-btn btn-wa" href="https://wa.me/${{waNum}}">💬 WhatsApp</a>`;
        }}
        if (lead.email) {{
            contactBtns += `<a class="contact-btn btn-email" href="mailto:${{lead.email}}">✉️ Email</a>`;
        }}
        if (lead.linkedin || lead.source_url) {{
            const url = lead.linkedin || lead.source_url;
            contactBtns += `<a class="contact-btn btn-li" href="${{url}}" target="_blank">🔗 Profile</a>`;
        }}
        
        return `
        <div class="lead-card ${{scoreClass}}">
            <div class="lead-name">${{lead.name || 'Unknown'}}</div>
            <div class="lead-score ${{scoreClass}}">${{scoreLabel}} — ${{lead.score}}/100</div>
            ${{lead.company ? `<div class="lead-detail">🏢 <span>${{lead.company}}</span></div>` : ''}}
            <div class="lead-detail">👤 <span>${{lead.investor_type || 'Investor'}}</span></div>
            <div class="lead-detail">📍 <span>${{lead.location || 'Unknown'}}</span></div>
            <div class="lead-detail">💰 <span>${{lead.budget_estimate || 'Unknown'}}</span></div>
            <div class="lead-detail">📡 <span>${{lead.source || 'Web'}}</span></div>
            ${{lead.phone ? `<div class="lead-detail">📱 <span>${{lead.phone}}</span></div>` : ''}}
            ${{lead.email ? `<div class="lead-detail">✉️ <span>${{lead.email}}</span></div>` : ''}}
            ${{lead.signal ? `<div class="lead-signal">"${{lead.signal.substring(0, 120)}}"</div>` : ''}}
            ${{contactBtns ? `<div class="contact-row">${{contactBtns}}</div>` : ''}}
        </div>`;
    }}).join('');
}}

async function runPipeline() {{
    const query = document.getElementById('queryInput').value.trim();
    if (!query) return;
    
    const btn = document.getElementById('runBtn');
    const statusBar = document.getElementById('statusBar');
    
    btn.disabled = true;
    btn.textContent = '⏳ Pipeline Running...';
    statusBar.className = 'status-bar active';
    statusBar.textContent = '🚀 Starting pipeline... This takes 3-5 minutes.';
    
    try {{
        const resp = await fetch('/run', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{query, max_leads: 20}})
        }});
        const data = await resp.json();
        currentJobId = data.job_id;
        
        statusBar.textContent = `✅ Pipeline started (Job: ${{currentJobId.substring(0,8)}}...) — Checking every 30s`;
        
        // Poll for completion
        pollingInterval = setInterval(() => checkStatus(currentJobId), 30000);
        
    }} catch(e) {{
        statusBar.className = 'status-bar error';
        statusBar.textContent = '❌ Error starting pipeline: ' + e.message;
        btn.disabled = false;
        btn.textContent = '🚀 Find New Leads';
    }}
}}

async function checkStatus(jobId) {{
    const statusBar = document.getElementById('statusBar');
    try {{
        const resp = await fetch(`/status/${{jobId}}`);
        const job = await resp.json();
        
        if (job.status === 'done') {{
            clearInterval(pollingInterval);
            statusBar.className = 'status-bar done';
            statusBar.textContent = `✅ Done! Found ${{job.leads_found}} leads`;
            
            document.getElementById('runBtn').disabled = false;
            document.getElementById('runBtn').textContent = '🚀 Find New Leads';
            
            // Load fresh leads
            const leadsResp = await fetch(`/leads/${{jobId}}`);
            const leadsData = await leadsResp.json();
            renderLeads(leadsData.leads);
            
        }} else if (job.status === 'failed') {{
            clearInterval(pollingInterval);
            statusBar.className = 'status-bar error';
            statusBar.textContent = `❌ Pipeline failed: ${{job.error}}`;
            document.getElementById('runBtn').disabled = false;
            document.getElementById('runBtn').textContent = '🚀 Find New Leads';
            
        }} else {{
            const stage = job.current_stage || 'processing';
            statusBar.textContent = `⏳ Running: ${{stage}}... (checking every 30s)`;
        }}
    }} catch(e) {{
        console.error('Status check error:', e);
    }}
}}

// Load existing leads on page open
renderLeads(allLeads);
</script>
</body>
</html>"""
    return html
