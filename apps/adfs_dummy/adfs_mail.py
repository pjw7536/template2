"""로컬 테스트를 위한 메일 샌드박스 엔드포인트입니다."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Header, Query

from adfs_settings import DEFAULT_EMAIL
from adfs_stores import mail_store, rag_store, seed_all

router = APIRouter()


@router.get("/mail/messages")
async def list_dummy_mail() -> Dict[str, Any]:
    """수동 점검을 위한 더미 메일 메시지를 모두 반환합니다."""
    mail_store.ensure_drone_sop_mail()
    return {"count": len(mail_store.mailbox), "messages": list(mail_store.mailbox.values())}


@router.post("/mail/messages")
async def create_dummy_mail(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """더미 메일 항목을 생성하고 필요 시 더미 RAG 스토어에 등록합니다."""
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


@router.post("/mail/send")
async def send_dummy_mail(
    payload: Dict[str, Any] = Body(...),
    system_id: str | None = Query(None, alias="systemId"),
    login_user_login: str | None = Query(None, alias="loginUser.login"),
    dep_ticket: str | None = Header(None, alias="x-dep-ticket"),
) -> Dict[str, Any]:
    """로컬 테스트용 Knox 메일 발송 API를 모사합니다."""

    title = str(payload.get("title") or payload.get("subject") or "로컬 더미 발신").strip()
    sender = str(payload.get("senderMailAddress") or payload.get("sender") or DEFAULT_EMAIL).strip()
    content = str(payload.get("content") or payload.get("body") or "").strip()

    receiver_list = payload.get("receiverList")
    receivers: list[str] = []
    if isinstance(receiver_list, list):
        for entry in receiver_list:
            if not isinstance(entry, dict):
                continue
            email = str(entry.get("email") or "").strip()
            if email:
                receivers.append(email)

    if not receivers:
        fallback = str(payload.get("recipient") or payload.get("receiver") or DEFAULT_EMAIL).strip()
        if fallback:
            receivers.append(fallback)

    metadata = {
        "system_id": system_id,
        "login_user_login": login_user_login,
        "has_dep_ticket": bool(dep_ticket),
    }

    sent: list[Dict[str, Any]] = []
    for recipient in receivers:
        sent.append(
            mail_store.create_mail(
                subject=title,
                sender=sender,
                recipient=recipient,
                body_text=content or "(empty)",
                register_to_rag=False,
                metadata=metadata,
            )
        )

    return {"status": "ok", "sent": len(sent), "messages": sent}


@router.delete("/mail/messages/{mail_id}")
async def delete_dummy_mail(mail_id: int) -> Dict[str, Any]:
    """더미 메일 항목과 연결된 RAG 문서가 있으면 함께 삭제합니다."""
    return mail_store.delete_mail(mail_id)


@router.post("/mail/reset")
async def reset_dummy_mail() -> Dict[str, Any]:
    """메일함과 RAG 문서를 기본 시드 데이터로 초기화합니다."""
    seed_all()
    return {
        "status": "ok",
        "seeded": {
            "mail": len(mail_store.mailbox),
            "rag": rag_store.total_count(),
            "indexes": rag_store.index_counts(),
        },
    }
