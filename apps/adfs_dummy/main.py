"""외부 개발을 위한 FastAPI 기반 더미 ADFS/RAG 샌드박스입니다."""

from __future__ import annotations

from adfs_app import create_app

app = create_app()
