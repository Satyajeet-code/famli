"""
FastAPI application entry point.

Run with:
    uvicorn backend.main:app --reload --port 8000

Required environment variables (load via .env at project root):
    DATABASE_URL  - e.g. postgresql://user:pass@localhost:5432/famli
    GROQ_API_KEY  - Groq API key
    GROQ_MODEL    - optional, defaults to llama-3.3-70b-versatile
    JWT_SECRET    - signing secret for HS256 JWTs
"""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api import auth_routes, retirement_routes  # noqa: E402
from app.utils.logger import AppLogger  # noqa: E402

AppLogger.configure()
logger = AppLogger.get_logger(__file__)

app = FastAPI(title="Famli Retirement Chatbot", version="0.1.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_routes.router)
app.include_router(retirement_routes.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


logger.info("FastAPI application configured with auth + retirement routers")
