"""Gurt Entrypoint Runner.

Run with: python run.py
Automatically switches to the workspace virtual environment (.venv) if needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure execution in workspace virtual environment if available
venv_python = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    try:
        import reportlab
        import pypdf
        import fastapi
        import uvicorn
    except ImportError:
        # Re-launch with workspace virtual environment Python
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

import uvicorn
from gurt.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print(f"  {settings.app_name}")
    print(f"  Local URL:  http://localhost:{settings.port}")
    print(f"  Network:    http://127.0.0.1:{settings.port}")
    print(f"  Docs:       http://localhost:{settings.port}/docs")
    print(f"  Database:   {settings.db_path}")
    print(f"  LLM Model:  {settings.gemini_model}")
    print("=" * 60)
    reload = "--reload" in sys.argv
    uvicorn.run("gurt.api.server:app", host=settings.host, port=settings.port, reload=reload)
