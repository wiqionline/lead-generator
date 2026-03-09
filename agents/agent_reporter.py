"""
AGENT 6 — Report Generator
────────────────────────────
Specific task: Generate a clean summary report
of qualified leads, formatted for easy reading.

Output: Text report saved to database + returned via API
"""
from typing import List
from core.models import QualifiedLead


async def run_reporter_agent(leads: List[QualifiedLead], query: str) -> str:
    """
    AGENT 6 — Generate clean lead report.
    """
    if not leads:
        return f'No leads found for: "{query}". Try a broader query.'

    high   = [l for l in leads if l.score >= 80]
    medium = [l for l in leads if 60 <= l.score < 80]
    low    = [l for l in leads if l.score < 60]

    with_phone    = sum(1 for l in leads if l.phone)
    with_email    = sum(1 for l in leads if l.email)
    with_linkedin = sum(1 for l in leads if l.linkedin)

    sources = {}
    for l in leads:
        sources[l.source] = sources.get(l.source, 0) + 1

    report = f"""
╔══════════════════════════════════════════════╗
  LEAD GENERATION REPORT
  Query: "{query}"
╚══════════════════════════════════════════════╝

SUMMARY
────────────────────────────────
Total Leads      : {len(leads)}
🔥 Hot (80+)     : {len(high)}
🟡 Warm (60-79)  : {len(medium)}
🔵 Cold (<60)    : {len(low)}

CONTACT DETAILS FOUND
────────────────────────────────
📱 Phone Numbers : {with_phone}
✉️  Emails        : {with_email}
🔗 LinkedIn      : {with_linkedin}

SOURCES
────────────────────────────────
{chr(10).join(f"  {s}: {c} leads" for s, c in sorted(sources.items(), key=lambda x: -x[1]))}

TOP LEADS
────────────────────────────────"""

    for i, lead in enumerate(leads[:10], 1):
        score_emoji = "🔥" if lead.score >= 80 else "🟡" if lead.score >= 60 else "🔵"
        report += f"""
{i}. {score_emoji} {lead.name}  [{lead.score}/100]
   Type     : {lead.investor_type}
   Interest : {lead.interest}
   Budget   : {lead.budget_estimate}
   Location : {lead.location or 'Unknown'}
   Phone    : {lead.phone or '—'}
   Email    : {lead.email or '—'}
   LinkedIn : {lead.linkedin or lead.source_url or '—'}
   Signal   : "{(lead.signal or '')[:100]}"
   Action   : {lead.recommended_approach}
"""

    report += """
NEXT ACTIONS
────────────────────────────────
1. Call/WhatsApp all leads with phone numbers today
2. Email leads with email addresses a personalised note
3. Connect on LinkedIn with profile leads
4. Run again tomorrow for fresh Telegram signals
"""
    return report.strip()
