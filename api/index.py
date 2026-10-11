"""Точка входа для Vercel (если он не подхватил app.py сам)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402,F401
