from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from api.telegram_auth import auth_router

app = FastAPI(
    title="AI Real Estate Lead Generator",
    description="Multi-agent pipeline for finding qualified real estate investors",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)

@app.get("/")
async def root():
    return {
        "service": "AI Real Estate Lead Generator",
        "status": "running",
        "docs": "/docs",
        "telegram_setup": "POST /telegram/send-code → POST /telegram/verify-code"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        timeout_keep_alive=300
    )
