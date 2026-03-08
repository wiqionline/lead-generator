from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(
    title="AI Real Estate Lead Generator",
    description="Multi-agent pipeline for finding qualified real estate investors",
    version="1.0.0"
)

# Allow frontend dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {
        "service": "AI Real Estate Lead Generator",
        "docs": "/docs",
        "endpoints": {
            "run_pipeline": "POST /run",
            "check_status": "GET /status/{job_id}",
            "get_leads": "GET /leads",
            "health": "GET /health"
        }
    }

# ── For Railway/Render deployment ─────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
