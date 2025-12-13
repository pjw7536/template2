"""Mail sandbox endpoints for local testing."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from adfs_settings import DEFAULT_EMAIL
from adfs_stores import mail_store, rag_store, seed_all

router = APIRouter()


@router.get("/mail/messages")
async def list_dummy_mail() -> Dict[str, Any]:
    """Return all dummy mail messages for quick manual testing."""
    return {"count": len(mail_store.mailbox), "messages": list(mail_store.mailbox.values())}


@router.post("/mail/messages")
async def create_dummy_mail(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Create a dummy mail entry and optionally register it to the dummy RAG store."""
    subject = str(payload.get("subject") or "로컬 더미 메일").strip()
    sender = str(payload.get("sender") or "sender@example.com").strip()
    recipient = str(payload.get("recipient") or DEFAULT_EMAIL).strip()
    body_text = str(payload.get("body") or payload.get("content") or "본문이 비어 있습니다.").strip()
    message_id = str(payload.get("message_id") or "").strip() or None
    received_at = str(payload.get("received_at") or "").strip() or None
    permission_groups = payload.get("permission_groups")
    register_to_rag = bool(payload.get("register_to_rag", True))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    if permission_groups and not isinstance(permission_groups, list):
        permission_groups = None

    entry = mail_store.create_mail(
        subject=subject,
        sender=sender,
        recipient=recipient,
        body_text=body_text,
        message_id=message_id,
        received_at=received_at,
        register_to_rag=register_to_rag,
        permission_groups=permission_groups,
        metadata=metadata,
    )

    return {"status": "ok", "message": entry}


@router.delete("/mail/messages/{mail_id}")
async def delete_dummy_mail(mail_id: int) -> Dict[str, Any]:
    """Remove a dummy mail entry and its paired RAG doc if present."""
    return mail_store.delete_mail(mail_id)


@router.post("/mail/reset")
async def reset_dummy_mail() -> Dict[str, Any]:
    """Reset mailbox and RAG docs to the default seed data."""
    seed_all()
    return {
        "status": "ok",
        "seeded": {
            "mail": len(mail_store.mailbox),
            "rag": rag_store.total_count(),
            "indexes": rag_store.index_counts(),
        },
    }

