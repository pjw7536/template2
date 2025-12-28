from __future__ import annotations

import base64
import hashlib
import logging
import os
import poplib
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Tuple

from django.utils import timezone

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from ..models import Email
from ..selectors import resolve_email_affiliation
from .rag import enqueue_rag_index, register_missing_rag_docs
from .storage import save_parsed_email
from .utils import _normalize_participants

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDED_SUBJECT_PREFIXES = ("[drone_sop]", "[test]")


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


def _format_display_address(*, name: str, address: str) -> str:
    """(name, address) 튜플을 사람이 읽기 좋은 "Name <addr>" 형식 문자열로 정규화합니다."""

    normalized_name = " ".join(str(name or "").split()).strip()
    normalized_address = str(address or "").strip()
    if normalized_name and normalized_address:
        return f"{normalized_name} <{normalized_address}>"
    return normalized_address or normalized_name


def _extract_participants(msg: Message, header_name: str) -> list[str]:
    """메일 헤더(To/Cc 등)에서 수신자 리스트를 파싱해 반환합니다."""

    raw_values = msg.get_all(header_name, []) or []
    decoded_values = [_decode_header_value(value) for value in raw_values if value]
    parsed = getaddresses(decoded_values)

    results: list[str] = []
    for name, address in parsed:
        formatted = _format_display_address(name=name, address=address)
        if formatted:
            results.append(formatted)
    return _normalize_participants(results)


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
    recipient = _extract_participants(msg, "To") or _extract_participants(msg, "Delivered-To")
    cc = _extract_participants(msg, "Cc")
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
        "cc": cc,
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
            classification_source = affiliation["classification_source"]
            rag_index_status = (
                Email.RagIndexStatus.PENDING
                if classification_source == Email.ClassificationSource.CONFIRMED_USER
                else Email.RagIndexStatus.SKIPPED
            )

            email_obj = save_parsed_email(
                message_id=fields["message_id"],
                received_at=received_at,
                subject=fields["subject"],
                sender=fields["sender"],
                sender_id=sender_id,
                recipient=fields["recipient"],
                cc=fields["cc"],
                user_sdwt_prod=user_sdwt_prod,
                classification_source=classification_source,
                rag_index_status=rag_index_status,
                body_text=fields.get("body_text") or "",
                body_html=fields.get("body_html"),
            )

            to_delete.append(msg_num)

            if (
                not email_obj.rag_doc_id
                and email_obj.user_sdwt_prod != UNASSIGNED_USER_SDWT_PROD
                and email_obj.classification_source == Email.ClassificationSource.CONFIRMED_USER
                and email_obj.rag_index_status == Email.RagIndexStatus.PENDING
            ):
                try:
                    enqueue_rag_index(email=email_obj)
                except Exception:
                    logger.exception("Failed to enqueue RAG outbox for email %s", email_obj.id)

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
