"""FastAPI-based dummy ADFS/RAG sandbox for external development."""

from __future__ import annotations

from adfs_app import create_app

app = create_app()
