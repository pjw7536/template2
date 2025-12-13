"""FastAPI app assembly (routers + shared state)."""

from __future__ import annotations

from fastapi import FastAPI

from adfs_llm import router as llm_router
from adfs_mail import router as mail_router
from adfs_oidc import router as oidc_router
from adfs_rag import router as rag_router
from adfs_settings import APP_TITLE, APP_VERSION
from adfs_stores import seed_all


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.include_router(oidc_router)
    app.include_router(llm_router)
    app.include_router(mail_router)
    app.include_router(rag_router)
    seed_all()
    return app
