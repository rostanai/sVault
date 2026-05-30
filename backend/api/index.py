"""Vercel Python serverless entrypoint.

Vercel exposes the ASGI `app` object. `vercel.json` routes all /api/* to this.
"""
import sys
from pathlib import Path

# Ensure the backend package is importable when Vercel runs this file.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

# Vercel's Python runtime serves this ASGI callable.
__all__ = ["app"]
