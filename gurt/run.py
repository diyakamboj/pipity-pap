"""Gurt Entrypoint Runner.

Run with: python run.py
"""

import sys
import uvicorn
from gurt.config import settings

if __name__ == "__main__":
    print(f"============================================================")
    print(f"  {settings.app_name}")
    print(f"  Local URL:  http://localhost:{settings.port}")
    print(f"  Network:    http://127.0.0.1:{settings.port}")
    print(f"  Docs:       http://localhost:{settings.port}/docs")
    print(f"  Database:   {settings.db_path}")
    print(f"  LLM Model:  {settings.gemini_model}")
    print(f"============================================================")
    reload = "--reload" in sys.argv
    uvicorn.run("gurt.api.server:app", host=settings.host, port=settings.port, reload=reload)
