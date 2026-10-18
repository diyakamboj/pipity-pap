"""Gurt - Event Operations Agent Configuration.

Independently implemented configuration loader.
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
DB_PATH = ROOT_DIR / "gurt_events.db"

# Load local environment
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Also check parent if running from workspace
    parent_env = ROOT_DIR.parent / "ClosedAI-main" / "chat_interface" / ".env.local"
    if parent_env.exists():
        load_dotenv(parent_env)


class Settings(BaseModel):
    app_name: str = "Gurt — Event Operations Agent"
    port: int = int(os.getenv("PORT", "8000"))
    host: str = os.getenv("HOST", "0.0.0.0")

    # LLM Settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    grok_api_key: str = os.getenv("GROK_API_KEY", "")

    # Tool Services
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    # Supabase (optional cloud persistence)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")

    db_path: Path = DB_PATH


settings = Settings()
