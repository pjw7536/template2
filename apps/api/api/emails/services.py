from __future__ import annotations

import base64
import hashlib
import gzip
import logging
import os
import poplib
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import requests
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from django.db import models
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .selectors import (
    get_next_user_sdwt_prod_change_effective_from,
    list_emails_by_ids,
    list_unassigned_email_ids_for_sender_id,
    resolve_email_affiliation,
    resolve_user_affiliation,
)
from .models import Email
from ..rag.client import delete_rag_doc, insert_email_to_rag, resolve_rag_index_name

logger = logging.getLogger(__name__)


class MailSendError(Exception):
    """사내 메일 발신 API 호출 실패 예외."""


def send_knox_mail_api(
    sender_email: str,
    receiver_emails: Sequence[str],
    subject: str,
    html_content: str,
) -> Dict[str, Any]:
    """사내 Knox 메일 발신 API를 호출해 메일을 발송합니다.

    Env:
    - MAIL_API_URL: 발신 API URL (예: https://.../send)
    - MAIL_API_KEY: x-dep-ticket 값
    - MAIL_API_SYSTEM_ID: systemId (default: plane)
    - MAIL_API_KNOX_ID: loginUser.login 값

    Returns:
    - API가 JSON을 반환하면 해당 dict
    - JSON이 아니면 {"ok": True}

    Side effects:
    - 외부 메일 발신 API에 HTTP 요청을 전송합니다.
    """

    url = (os.getenv("MAIL_API_URL") or "").strip()
    prod_key = (os.getenv("MAIL_API_KEY") or "").strip()
    system_id = (os.getenv("MAIL_API_SYSTEM_ID") or "plane").strip()
    knox_id = (os.getenv("MAIL_API_KNOX_ID") or "").strip()

    if not url:
        raise MailSendError("MAIL_API_URL 미설정")
    if not prod_key or not knox_id:
        raise MailSendError("MAIL_API_KEY / MAIL_API_KNOX_ID 미설정")

    normalized_receivers = [str(email).strip() for email in receiver_emails if str(email).strip()]
    if not normalized_receivers:
        raise MailSendError("수신자 없음")

    params = {"systemId": system_id, "loginUser.login": knox_id}
    headers = {"x-dep-ticket": prod_key}
    payload = {
        "receiverList": [{"email": email, "recipientType": "TO"} for email in normalized_receivers],
        "title": subject,
        "content": html_content,
        "senderMailAddress": sender_email,
    }

    try:
        response = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
        if not response.ok:
            raise MailSendError(f"메일 API 오류 {response.status_code}: {response.text[:300]}")
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"data": data}
        return {"ok": True}
    except requests.Timeout as exc:
        raise MailSendError("메일 API 타임아웃") from exc
    except requests.RequestException as exc:
        raise MailSendError(f"메일 API 요청 실패: {exc}") from exc


def gzip_body(body_html: str | None) -> bytes | None:
    """HTML 문자열을 gzip 압축하여 BinaryField에 저장 가능하도록 변환."""

    if not body_html:
        return None
    return gzip.compress(body_html.encode("utf-8"))


def save_parsed_email(
    *,
    message_id: str,
    received_at: datetime | None,
    subject: str,
    sender: str,
    sender_id: str,
    recipient: str,
    user_sdwt_prod: str | None,
    body_html: str | None,
    body_text: str | None,
) -> Email:
    """POP3 파서에서 호출하는 저장 함수 (message_id 중복 방지)."""

    user_sdwt_prod = user_sdwt_prod or UNASSIGNED_USER_SDWT_PROD

    email, _created = Email.objects.get_or_create(
        message_id=message_id,
        defaults={
            "received_at": received_at or timezone.now(),
            "subject": subject,
            "sender": sender,
            "sender_id": sender_id,
            "recipient": recipient,
            "user_sdwt_prod": user_sdwt_prod,
            "body_text": body_text or "",
            "body_html_gzip": gzip_body(body_html),
        },
    )
    if not _created:
        fields_to_update = []
        if not email.sender_id:
            email.sender_id = sender_id
            fields_to_update.append("sender_id")
        if not email.user_sdwt_prod and user_sdwt_prod:
            email.user_sdwt_prod = user_sdwt_prod
            fields_to_update.append("user_sdwt_prod")
        if fields_to_update:
            email.save(update_fields=fields_to_update)
    return email


def register_email_to_rag(
    email: Email,
    previous_user_sdwt_prod: str | None = None,
    persist_fields: Sequence[str] | None = None,
) -> Email:
    """
    이메일을 RAG에 등록하고 rag_doc_id를 저장.
    - 이미 rag_doc_id가 있으면 그대로 사용.
    - 실패 시 예외를 발생시켜 호출 측에서 재시도 가능.
    - previous_user_sdwt_prod가 주어지면, 인덱스가 달라진 경우 이전 인덱스 문서를 삭제 후 재삽입
    """

    update_fields = []
    normalized_user_sdwt = (email.user_sdwt_prod or "").strip()
    if not normalized_user_sdwt or normalized_user_sdwt == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot register an UNASSIGNED email to RAG")
    if normalized_user_sdwt != email.user_sdwt_prod:
        email.user_sdwt_prod = normalized_user_sdwt
        update_fields.append("user_sdwt_prod")
    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
        update_fields.append("rag_doc_id")

    new_index = resolve_rag_index_name(email.user_sdwt_prod)
    previous_index = (
        resolve_rag_index_name(previous_user_sdwt_prod)
        if previous_user_sdwt_prod is not None
        else new_index
    )

    if email.rag_doc_id and previous_user_sdwt_prod is not None and previous_index != new_index:
        try:
            delete_rag_doc(email.rag_doc_id, index_name=previous_index)
        except Exception:
            logger.exception(
                "Failed to delete previous RAG doc for email id=%s (index=%s)", email.id, previous_index
            )

    target_index = new_index
    insert_email_to_rag(email, index_name=target_index)
    if persist_fields:
        update_fields.extend(list(persist_fields))
    if update_fields:
        email.save(update_fields=list(dict.fromkeys(update_fields)))  # deduplicate
    return email


def register_missing_rag_docs(limit: int = 500) -> int:
    """
    rag_doc_id가 없는 이메일을 다시 RAG에 등록 시도한다.
    - POP3 삭제 이후 RAG 등록 실패 건을 재시도하기 위한 백필용.
    """

    pending = list(
        Email.objects.filter(models.Q(rag_doc_id__isnull=True) | models.Q(rag_doc_id="")).order_by("id")[:limit]
    )
    registered = 0

    for email in pending:
        try:
            register_email_to_rag(email)
            registered += 1
        except Exception:
            logger.exception("Failed to register missing RAG doc for email id=%s", email.id)

    return registered


@transaction.atomic
def delete_single_email(email_id: int) -> Email:
    """단일 메일 삭제 (RAG 삭제 실패 시 전체 롤백)."""

    try:
        email = Email.objects.select_for_update().get(id=email_id)
    except Email.DoesNotExist:
        raise NotFound("Email not found")

    if email.rag_doc_id:
        delete_rag_doc(email.rag_doc_id, index_name=resolve_rag_index_name(email.user_sdwt_prod))  # 실패 시 예외 발생 → 트랜잭션 롤백

    email.delete()
    return email


@transaction.atomic
def bulk_delete_emails(email_ids: List[int]) -> int:
    """여러 메일을 한 번에 삭제 (all-or-nothing)."""

    emails = list(Email.objects.select_for_update().filter(id__in=email_ids))
    if not emails:
        raise NotFound("No emails found to delete")

    for email in emails:
        if email.rag_doc_id:
            delete_rag_doc(email.rag_doc_id, index_name=resolve_rag_index_name(email.user_sdwt_prod))  # 실패 시 예외 → 전체 롤백

    target_ids = [email.id for email in emails]
    Email.objects.filter(id__in=target_ids).delete()

    return len(emails)


def reclassify_emails_for_user_sdwt_change(user: Any, effective_from: datetime | None) -> int:
    """Reclassify emails after a user's user_sdwt_prod changes.

    대상:
    - sender_id == user.knox_id (없으면 user.sabun) 인 메일
    범위:
    - effective_from 이상, 다음 변경 시점 이전(있으면)

    Returns:
        Reclassified email count.

    Side effects:
        - Updates Email.user_sdwt_prod in DB.
        - Re-indexes RAG documents per email.
    """

    if effective_from is None:
        effective_from = timezone.now()

    start = effective_from
    end = get_next_user_sdwt_prod_change_effective_from(user=user, effective_from=effective_from)

    resolved_sender_id = getattr(user, "knox_id", None)
    if not isinstance(resolved_sender_id, str) or not resolved_sender_id.strip():
        resolved_sender_id = getattr(user, "sabun", None) or getattr(user, "get_username", lambda: None)()

    if not isinstance(resolved_sender_id, str) or not resolved_sender_id.strip():
        return 0

    queryset = Email.objects.filter(sender_id=resolved_sender_id, received_at__gte=start)
    if end is not None:
        queryset = queryset.filter(received_at__lt=end)

    previous_user_sdwt = {
        row["id"]: row["user_sdwt_prod"] for row in queryset.values("id", "user_sdwt_prod")
    }
    ids = list(previous_user_sdwt.keys())
    if not ids:
        return 0

    affiliation = resolve_user_affiliation(user, effective_from)
    user_sdwt_prod = affiliation.get("user_sdwt_prod") or UNASSIGNED_USER_SDWT_PROD

    with transaction.atomic():
        Email.objects.filter(id__in=ids).update(
            user_sdwt_prod=user_sdwt_prod,
        )

        for email in Email.objects.filter(id__in=ids).iterator():
            email.user_sdwt_prod = user_sdwt_prod
            try:
                register_email_to_rag(
                    email,
                    previous_user_sdwt_prod=previous_user_sdwt.get(email.id),
                    persist_fields=["user_sdwt_prod", "rag_doc_id"],
                )
            except Exception:
                logger.exception("Failed to reinsert RAG for email id=%s", email.id)

    return len(ids)


def claim_unassigned_emails_for_user(*, user: Any) -> Dict[str, int]:
    """사용자의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다.

    Claim UNASSIGNED inbox emails for the given user into the user's current user_sdwt_prod.

    Rules:
    - Only emails with user_sdwt_prod not set (NULL/blank/UNASSIGNED) are eligible.
    - Previously classified emails are NOT moved.

    Returns:
        Dict with moved count and best-effort RAG indexing stats.

    Side effects:
        - Updates Email.user_sdwt_prod in DB.
        - Attempts to index claimed emails into RAG (best-effort).
    """

    sender_id = getattr(user, "knox_id", None)
    if not isinstance(sender_id, str) or not sender_id.strip():
        raise ValueError("knox_id is required to claim unassigned emails")

    target_user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
    if not isinstance(target_user_sdwt_prod, str) or not target_user_sdwt_prod.strip():
        raise ValueError("user_sdwt_prod must be set to claim unassigned emails")

    target_user_sdwt_prod = target_user_sdwt_prod.strip()
    if target_user_sdwt_prod == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot claim emails into the UNASSIGNED mailbox")

    email_ids = list_unassigned_email_ids_for_sender_id(sender_id=sender_id)
    if not email_ids:
        return {"moved": 0, "ragRegistered": 0, "ragFailed": 0}

    with transaction.atomic():
        Email.objects.filter(id__in=email_ids).update(user_sdwt_prod=target_user_sdwt_prod)

    rag_registered = 0
    rag_failed = 0
    for email in list_emails_by_ids(email_ids=email_ids).iterator():
        email.user_sdwt_prod = target_user_sdwt_prod
        try:
            register_email_to_rag(
                email,
                previous_user_sdwt_prod=None,
                persist_fields=["user_sdwt_prod", "rag_doc_id"],
            )
            rag_registered += 1
        except Exception:
            rag_failed += 1
            logger.exception("Failed to register RAG for claimed email id=%s", email.id)
            if not email.rag_doc_id:
                email.rag_doc_id = f"email-{email.id}"
            try:
                email.save(update_fields=["user_sdwt_prod", "rag_doc_id"])
            except Exception:
                logger.exception("Failed to persist claimed email after RAG failure id=%s", email.id)

    return {"moved": len(email_ids), "ragRegistered": rag_registered, "ragFailed": rag_failed}


DEFAULT_EXCLUDED_SUBJECT_PREFIXES = ("[drone_sop_v3]", "[test]")


def _load_excluded_subject_prefixes() -> tuple[str, ...]:
    """환경변수 기반 메일 제목 제외 prefix 목록을 로드합니다."""

    raw = os.getenv("EMAIL_EXCLUDED_SUBJECT_PREFIXES", "")
    if not raw:
        return DEFAULT_EXCLUDED_SUBJECT_PREFIXES

    prefixes: List[str] = []
    for item in raw.split(","):
        cleaned = item.strip().strip("\"'").lower()
        if cleaned:
            prefixes.append(cleaned)

    return tuple(prefixes) if prefixes else DEFAULT_EXCLUDED_SUBJECT_PREFIXES


EXCLUDED_SUBJECT_PREFIXES = _load_excluded_subject_prefixes()


def _is_excluded_subject(subject: str) -> bool:
    """제목이 제외 대상 prefix로 시작하는지 검사합니다."""

    normalized = (subject or "").strip().lower()
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_SUBJECT_PREFIXES)


def _decode_header_value(raw_value: str | None) -> str:
    """RFC2047 인코딩 헤더 값을 사람이 읽을 수 있는 문자열로 디코딩합니다."""

    if not raw_value:
        return ""
    try:
        return str(make_header(decode_header(raw_value)))
    except Exception:
        return raw_value


def _decode_part(part: Message) -> str:
    """메일 MIME 파트의 payload를 charset 기반으로 문자열 디코딩합니다."""

    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _replace_cid_images(soup: Any, cid_map: Dict[str, Dict[str, Any]]) -> None:
    """HTML 본문 내 cid: 이미지 참조를 data URI로 치환합니다."""

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("cid:"):
            continue
        cid = src[4:]
        if cid not in cid_map:
            continue
        data = cid_map[cid].get("data")
        img_type = cid_map[cid].get("type") or "png"
        if not data:
            continue
        b64 = base64.b64encode(data).decode("utf-8")
        img["src"] = f"data:image/{img_type};base64,{b64}"


def _replace_mosaic_embeds(soup: Any) -> None:
    """모자이크(https://mosaic...) embed를 링크로 치환해 렌더링 문제를 완화합니다."""

    for embed in soup.find_all("embed"):
        src = embed.get("src", "")
        if not src.startswith("https://mosaic"):
            continue
        parent_div = embed.find_parent("div")
        if parent_div:
            span_tag = soup.new_tag("span")
            a_tag = soup.new_tag("a", href=src)
            a_tag.string = "모자이크 링크"
            span_tag.append(a_tag)
            parent_div.replace_with(span_tag)


def _extract_bodies(msg: Message) -> Tuple[str, str]:
    """메일 메시지에서 텍스트/HTML 본문을 추출하고(가능하면) 정규화합니다."""

    text_body = ""
    html_content = ""
    cid_map: Dict[str, Dict[str, Any]] = {}

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            content_type = part.get_content_type()
            disposition = (part.get("Content-Disposition") or "").lower()
            content_id = part.get("Content-ID")

            if content_type.startswith("image/") and content_id:
                payload = part.get_payload(decode=True)
                if payload:
                    cid_map[content_id.strip("<>")] = {
                        "data": payload,
                        "type": part.get_content_subtype(),
                    }
                continue

            if disposition.startswith("attachment"):
                continue

            if content_type == "text/plain" and not text_body:
                text_body = _decode_part(part)
            elif content_type == "text/html" and not html_content:
                html_content = _decode_part(part)
    else:
        content_type = msg.get_content_type()
        disposition = (msg.get("Content-Disposition") or "").lower()
        content_id = msg.get("Content-ID")

        if content_type.startswith("image/") and content_id:
            payload = msg.get_payload(decode=True)
            if payload:
                cid_map[content_id.strip("<>")] = {
                    "data": payload,
                    "type": msg.get_content_subtype(),
                }

        if not disposition.startswith("attachment"):
            if content_type == "text/plain":
                text_body = _decode_part(msg)
            elif content_type == "text/html":
                html_content = _decode_part(msg)

    if html_content:
        from bs4 import BeautifulSoup  # dependency used only for ingest

        soup = BeautifulSoup(html_content, "lxml")
        _replace_cid_images(soup, cid_map)
        _replace_mosaic_embeds(soup)
        body_html = soup.prettify()
        body_text = soup.get_text()
        return body_text, body_html

    if not text_body and hasattr(msg, "get_body"):
        try:
            fallback = msg.get_body(preferencelist=("plain", "html"))
            if fallback:
                text_body = _decode_part(fallback)
        except Exception:
            pass

    return text_body or "", ""


def _parse_received_at(msg: Message) -> datetime:
    """메일 Date 헤더를 파싱해 수신 시각(timezone-aware)을 반환합니다."""

    raw_date = msg.get("Date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed and timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            if parsed:
                return parsed
        except Exception:
            logger.exception("Failed to parse email Date header: %s", raw_date)
    return timezone.now()


def _extract_subject_header(msg: Message) -> str:
    """메일 Subject 헤더를 디코딩해 반환합니다."""

    return _decode_header_value(msg.get("Subject"))


def _extract_sender_id(sender: str) -> str:
    """발신자 주소 문자열에서 sender_id(로컬파트)를 추출합니다."""

    address = parseaddr(sender or "")[1]
    if address and "@" in address:
        local = address.split("@", 1)[0].strip()
        if local:
            return local
    normalized = (sender or "").strip()
    return normalized or "UNKNOWN"


def _parse_message_to_fields(msg: Message) -> Dict[str, Any]:
    """메일 Message 객체를 Email 저장에 필요한 필드 dict로 변환합니다."""

    subject = _extract_subject_header(msg)
    sender = _decode_header_value(msg.get("From"))
    recipient = _decode_header_value(msg.get("To") or msg.get("Delivered-To") or "")
    message_id = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if not message_id:
        content_hash = hashlib.sha256(msg.as_bytes()).hexdigest()
        message_id = f"generated-{content_hash}"

    body_text, body_html = _extract_bodies(msg)
    received_at = _parse_received_at(msg)
    sender_id = _extract_sender_id(sender)

    return {
        "message_id": message_id,
        "received_at": received_at,
        "subject": subject,
        "sender": sender,
        "sender_id": sender_id,
        "recipient": recipient,
        "body_text": body_text,
        "body_html": body_html,
    }


def _iter_pop3_messages(session: Any) -> Iterable[Tuple[int, Message]]:
    """POP3 세션에서 (메시지 번호, Message) 스트림을 생성합니다."""

    if hasattr(session, "iter_messages"):
        yield from session.iter_messages()
        return

    _resp, items, _octets = session.list()
    if not items:
        return

    for item in items:
        raw = item.decode() if isinstance(item, (bytes, bytearray)) else str(item)
        msg_num = int(raw.split()[0])
        _resp, lines, _octets = session.retr(msg_num)
        raw_msg = b"\n".join(lines)
        msg = BytesParser(policy=default).parsebytes(raw_msg)
        yield msg_num, msg


def _delete_pop3_messages(session: Any, message_numbers: List[int]) -> None:
    """POP3 세션에서 지정한 메시지 번호들을 삭제(mark)합니다."""

    if not message_numbers:
        return

    for msg_num in message_numbers:
        try:
            session.dele(msg_num)
        except Exception:
            logger.exception("Failed to delete POP3 message #%s", msg_num)


def ingest_pop3_mailbox(session: Any) -> List[int]:
    """
    POP3 메일함을 순회하며 Email + RAG 등록 후 삭제 대상 번호를 반환.
    - 제목 제외 규칙을 최상단에서 처리
    - DB 저장 성공 시에만 POP3 삭제
    - RAG 등록 실패는 POP3 삭제 여부에 영향을 주지 않음
    """

    to_delete: List[int] = []

    for msg_num, msg in _iter_pop3_messages(session):
        try:
            subject = _extract_subject_header(msg)
            if _is_excluded_subject(subject):
                logger.info("Skipping excluded email subject: %s", subject)
                continue

            fields = _parse_message_to_fields(msg)
            sender_id = fields["sender_id"]
            received_at = fields["received_at"]
            affiliation = resolve_email_affiliation(sender_id=sender_id, received_at=received_at)
            user_sdwt_prod = affiliation["user_sdwt_prod"]

            email_obj = save_parsed_email(
                message_id=fields["message_id"],
                received_at=received_at,
                subject=fields["subject"],
                sender=fields["sender"],
                sender_id=sender_id,
                recipient=fields["recipient"],
                user_sdwt_prod=user_sdwt_prod,
                body_text=fields.get("body_text") or "",
                body_html=fields.get("body_html"),
            )

            to_delete.append(msg_num)

            if not email_obj.rag_doc_id and email_obj.user_sdwt_prod != UNASSIGNED_USER_SDWT_PROD:
                try:
                    register_email_to_rag(email_obj)
                except Exception:
                    logger.exception("RAG insert failed for email %s, will retry later", email_obj.id)

        except Exception as exc:
            logger.exception("Failed to process POP3 message #%s: %s", msg_num, exc)
            continue

    _delete_pop3_messages(session, to_delete)
    return to_delete


def run_pop3_ingest(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    timeout: int = 60,
) -> Dict[str, int]:
    """POP3 세션을 열어 메일을 수집/저장하고 삭제를 커밋합니다.

    Create a POP3 session, ingest messages, and commit deletions.

    Args:
        host: POP3 server host.
        port: POP3 port.
        username: POP3 login username.
        password: POP3 login password.
        use_ssl: Use POP3_SSL when True.
        timeout: Socket timeout seconds.

    Returns:
        Dict with deleted message count and reindexed count.

    Side effects:
        - Reads from POP3 mailbox.
        - Writes Email rows and RAG documents.
        - Deletes messages from POP3 mailbox (commit via quit()).
    """

    if not host or not username or not password:
        raise ValueError("POP3 connection info is incomplete (host/username/password required)")

    client_cls = poplib.POP3_SSL if use_ssl else poplib.POP3
    client = client_cls(host, port, timeout=timeout)
    deleted: List[int] = []
    reindexed = 0
    try:
        client.user(username)
        client.pass_(password)
        logger.info("POP3 login succeeded: host=%s port=%s ssl=%s", host, port, use_ssl)

        deleted = ingest_pop3_mailbox(client) or []
        try:
            reindexed = register_missing_rag_docs()
            if reindexed:
                logger.info("RAG backfill attempted for %s emails without rag_doc_id", reindexed)
        except Exception:
            logger.exception("RAG backfill failed after POP3 ingest")
        logger.info("Ingest complete; marked %s messages for deletion", len(deleted))

        client.quit()
        logger.info("POP3 session closed (quit)")
    except Exception:
        logger.exception("POP3 ingest failed; rolling back via rset()")
        try:
            client.rset()
        except Exception:
            logger.debug("POP3 rset failed")
        raise
    finally:
        try:
            client.quit()
        except Exception:
            pass

    return {"deleted": len(deleted), "reindexed": reindexed}


def _env_bool(key: str, default: bool = False) -> bool:
    """환경변수 값을 boolean으로 파싱합니다."""

    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run_pop3_ingest_from_env() -> Dict[str, int]:
    """환경변수로 POP3 수집을 실행합니다.

    Run POP3 ingest using environment variables.

    Env keys (new preferred):
    - EMAIL_POP3_HOST / EMAIL_POP3_PORT / EMAIL_POP3_USERNAME / EMAIL_POP3_PASSWORD
    - EMAIL_POP3_USE_SSL / EMAIL_POP3_TIMEOUT

    Fallback keys:
    - POP3_HOST / POP3_PORT / POP3_USERNAME / POP3_PASSWORD / POP3_USE_SSL / POP3_TIMEOUT
    """

    host = os.getenv("EMAIL_POP3_HOST") or os.getenv("POP3_HOST") or ""
    port = int(os.getenv("EMAIL_POP3_PORT") or os.getenv("POP3_PORT") or "995")
    username = os.getenv("EMAIL_POP3_USERNAME") or os.getenv("POP3_USERNAME") or ""
    password = os.getenv("EMAIL_POP3_PASSWORD") or os.getenv("POP3_PASSWORD") or ""
    use_ssl = _env_bool("EMAIL_POP3_USE_SSL", _env_bool("POP3_USE_SSL", True))
    timeout = int(os.getenv("EMAIL_POP3_TIMEOUT") or os.getenv("POP3_TIMEOUT") or "60")

    return run_pop3_ingest(
        host=host,
        port=port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        timeout=timeout,
    )
