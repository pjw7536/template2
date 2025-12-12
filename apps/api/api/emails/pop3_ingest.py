from __future__ import annotations

import base64
import hashlib
import logging
import os
import poplib
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Tuple

from bs4 import BeautifulSoup
from django.utils import timezone

from .affiliation import resolve_email_affiliation
from .services import register_email_to_rag, register_missing_rag_docs, save_parsed_email

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDED_SUBJECT_PREFIXES = ("[drone_sop_v3]", "[test]")


def _load_excluded_subject_prefixes() -> tuple[str, ...]:
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


def is_excluded_subject(subject: str) -> bool:
    normalized = (subject or "").strip().lower()
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_SUBJECT_PREFIXES)


def _decode_header_value(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    try:
        return str(make_header(decode_header(raw_value)))
    except Exception:
        return raw_value


def replace_cid_images(soup: BeautifulSoup, cid_map: Dict[str, Dict[str, Any]]) -> None:
    """
    cid 기반 이미지를 base64 data URI로 변환한다.
    """

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


def replace_mosaic_embeds(soup: BeautifulSoup) -> None:
    """
    mosaic embed 태그를 링크로 교체한다.
    """

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


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _extract_bodies(msg: Message) -> Tuple[str, str]:
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
        soup = BeautifulSoup(html_content, "lxml")
        replace_cid_images(soup, cid_map)
        replace_mosaic_embeds(soup)
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


def _parse_received_at(msg: Message):
    raw_date = msg.get("Date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed and timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.utc)
            return parsed
        except Exception:
            logger.exception("Failed to parse email Date header: %s", raw_date)
    return timezone.now()


def extract_subject_header(msg: Message) -> str:
    return _decode_header_value(msg.get("Subject"))


def extract_sender_id(sender: str) -> str:
    """
    발신자 문자열에서 계정 ID/사번 등을 추출.
    - 이메일 주소일 경우 local-part를 사용
    - 그 외에는 원본 문자열을 이용하며, 비어 있으면 UNKNOWN 반환
    """

    address = parseaddr(sender or "")[1]
    if address and "@" in address:
        local = address.split("@", 1)[0].strip()
        if local:
            return local
    normalized = (sender or "").strip()
    return normalized or "UNKNOWN"


def parse_message_to_fields(msg: Message) -> Dict[str, Any]:
    subject = extract_subject_header(msg)
    sender = _decode_header_value(msg.get("From"))
    recipient = _decode_header_value(msg.get("To") or msg.get("Delivered-To") or "")
    message_id = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if not message_id:
        # POP3 메시지가 message-id를 제공하지 않는 경우 내용 해시로 결정론적 ID 생성
        content_hash = hashlib.sha256(msg.as_bytes()).hexdigest()
        message_id = f"generated-{content_hash}"

    body_text, body_html = _extract_bodies(msg)
    received_at = _parse_received_at(msg)
    sender_id = extract_sender_id(sender)

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
    """poplib.POP3 호환 세션에서 메시지를 순회."""

    if hasattr(session, "iter_messages"):
        yield from session.iter_messages()
        return

    resp, items, _ = session.list()
    if not items:
        return

    for item in items:
        raw = item.decode() if isinstance(item, (bytes, bytearray)) else str(item)
        msg_num = int(raw.split()[0])
        _resp, lines, _ = session.retr(msg_num)
        raw_msg = b"\n".join(lines)
        msg = BytesParser(policy=default).parsebytes(raw_msg)
        yield msg_num, msg


def _delete_pop3_messages(session: Any, message_numbers: List[int]):
    if not message_numbers:
        return

    for msg_num in message_numbers:
        try:
            session.dele(msg_num)
        except Exception:
            logger.exception("Failed to delete POP3 message #%s", msg_num)
    # poplib의 경우 session.quit() 호출 시 실제 삭제가 커밋됨 (호출자는 책임 있게 종료 처리 필요)


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
            subject = extract_subject_header(msg)
            if is_excluded_subject(subject):
                logger.info("Skipping excluded email subject: %s", subject)
                continue

            fields = parse_message_to_fields(msg)
            sender_id = fields["sender_id"]
            received_at = fields["received_at"]
            affiliation = resolve_email_affiliation(sender_id, received_at)
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

            # RAG 등록 (중복 등록 방지)
            if not email_obj.rag_doc_id:
                try:
                    register_email_to_rag(email_obj)
                except Exception:
                    logger.exception("RAG insert failed for email %s, will retry later", email_obj.id)

        except Exception as exc:
            logger.exception("Failed to process POP3 message #%s: %s", msg_num, exc)
            continue

    _delete_pop3_messages(session, to_delete)
    return to_delete


def run_pop3_ingest(host: str, port: int, username: str, password: str, use_ssl: bool = True, timeout: int = 60):
    """
    POP3 세션 생성/정리까지 포함한 전체 ingest 진입점.
    Airflow 등 외부 오케스트레이터는 이 함수만 호출하면 된다.
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

        client.quit()  # commit deletions
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
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run_pop3_ingest_from_env():
    """
    환경 변수 기반으로 POP3 연결 정보를 읽어 ingest를 실행.
    Airflow DAG는 이 함수를 직접 호출한다.
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
