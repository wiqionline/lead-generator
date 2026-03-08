from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

class RawLead(BaseModel):
    name: str
    company: Optional[str] = None
    source_url: Optional[str] = None
    raw_text: str
    platform: str  # e.g. "google", "forum", "portal"

class QualifiedLead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    company: Optional[str] = None
    investor_type: Optional[str] = None  # HNWI, Institutional, Family Office, etc.
    interest: Optional[str] = None       # Off-plan, Luxury, etc.
    location: Optional[str] = None
    budget_estimate: Optional[str] = None
    signal: Optional[str] = None         # What triggered this lead
    score: int = 0                        # 0-100 qualification score
    score_reason: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    recommended_approach: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class PipelineJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    status: str = "pending"   # pending | running | done | failed
    current_stage: Optional[str] = None
    leads_found: int = 0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

class RunRequest(BaseModel):
    query: str = Field(..., description="Describe the investor profile to target")
    max_leads: int = Field(default=20, ge=1, le=50)
