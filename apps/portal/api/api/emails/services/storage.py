# =============================================================================
# 모듈 설명: 이메일 저장 및 MinIO HTML/자산 저장을 제공합니다.
# - 주요 함수: save_parsed_email, store_email_html_and_assets
# - 불변 조건: message_id는 중복 방지 키로 사용됩니다.
# =============================================================================

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from django.db import transaction
from django.utils import timezone

from api.common.services import UNASSIGNED_USER_SDWT_PROD
from api.common.services import delete_object, download_bytes, upload_bytes

from ..models import Email, EmailAsset
from .utils import _build_participants_search, _normalize_participants

# =============================================================================
# 로깅
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
ASSET_URL_PREFIX = "/api/v1/emails"
HTML_OBJECT_PREFIX = "html"
ASSET_OBJECT_PREFIX = "assets"
DATA_URL_PATTERN = re.compile(
    r"^data:(?P<type>[^;]+)(?:;[^;]+)*;base64,(?P<data>.+)$",
    re.IGNORECASE | re.DOTALL,
)
SRCSET_PATTERN = re.compile(r"\s*(\S+)(\s+\d+(?:\.\d+)?[wx])?\s*(?:,|$)")
CSS_URL_PATTERN = re.compile(r"url\(([^)]+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class EmailAssetPayload:
    sequence: int
    source: str
    content_type: str | None
    data: bytes | None
    original_url: str | None



def save_parsed_email(
    *,
    message_id: str,
    received_at: datetime | None,
    subject: str,
    sender: str,
    sender_id: str,
    recipient: Sequence[str] | None,
    cc: Sequence[str] | None,
    user_sdwt_prod: str | None,
    classification_source: str,
    rag_index_status: str,
    body_text: str | None,
) -> tuple[Email, bool]:
    """POP3 파서에서 호출하는 저장 함수입니다(message_id 중복 방지).

    입력:
        message_id: 이메일 고유 식별자.
        received_at: 수신 시각(없으면 현재 시각).
        subject/sender/sender_id: 제목/발신자 정보.
        recipient/cc: 수신/참조 목록.
        user_sdwt_prod: 메일함 식별자.
        classification_source: 분류 출처 코드.
        rag_index_status: RAG 인덱싱 상태.
        body_text: 본문 텍스트 데이터.
    반환:
        (저장/갱신된 Email, 생성 여부) 튜플.
    부작용:
        Email 테이블에 insert/update 수행.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 기본값/참여자 정규화
    # -----------------------------------------------------------------------------
    user_sdwt_prod = user_sdwt_prod or UNASSIGNED_USER_SDWT_PROD

    normalized_recipient = _normalize_participants(recipient)
    normalized_cc = _normalize_participants(cc)
    participants_search = _build_participants_search(recipient=normalized_recipient, cc=normalized_cc)

    # -----------------------------------------------------------------------------
    # 2) message_id 기준 upsert
    # -----------------------------------------------------------------------------
    email, _created = Email.objects.get_or_create(
        message_id=message_id,
        defaults={
            "received_at": received_at or timezone.now(),
            "subject": subject,
            "sender": sender,
            "sender_id": sender_id,
            "recipient": normalized_recipient or None,
            "cc": normalized_cc or None,
            "participants_search": participants_search,
            "user_sdwt_prod": user_sdwt_prod,
            "classification_source": classification_source,
            "rag_index_status": rag_index_status,
            "body_text": body_text or "",
        },
    )

    # -----------------------------------------------------------------------------
    # 3) 기존 레코드 보정 업데이트
    # -----------------------------------------------------------------------------
    if not _created:
        fields_to_update = []
        if not email.sender_id:
            email.sender_id = sender_id
            fields_to_update.append("sender_id")
        if not email.user_sdwt_prod and user_sdwt_prod:
            email.user_sdwt_prod = user_sdwt_prod
            fields_to_update.append("user_sdwt_prod")
        if classification_source and email.classification_source != classification_source:
            email.classification_source = classification_source
            fields_to_update.append("classification_source")
        if rag_index_status and email.rag_index_status != rag_index_status:
            email.rag_index_status = rag_index_status
            fields_to_update.append("rag_index_status")
        if fields_to_update:
            email.save(update_fields=fields_to_update)
    return email, _created


def _build_email_html_object_key(email_id: int) -> str:
    """Email HTML 저장용 오브젝트 키를 생성합니다."""

    return f"{HTML_OBJECT_PREFIX}/{email_id}.html"


def _build_email_asset_object_key(email_id: int, sequence: int, extension: str) -> str:
    """Email 이미지 자산 저장용 오브젝트 키를 생성합니다."""

    normalized = extension if extension.startswith(".") else f".{extension}"
    return f"{ASSET_OBJECT_PREFIX}/{email_id}/{sequence}{normalized}"


def _build_email_asset_url(email_id: int, sequence: int) -> str:
    """Email 이미지 자산 API URL을 생성합니다."""

    return f"{ASSET_URL_PREFIX}/{email_id}/assets/{sequence}/"


def _resolve_extension(*, content_type: str | None, original_url: str | None) -> str:
    """이미지 저장 확장자를 결정합니다.

    입력:
        content_type: MIME 타입.
        original_url: 원본 URL(옵션).
    반환:
        확장자 문자열(예: .png).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) MIME 타입 기반 매핑
    # -----------------------------------------------------------------------------
    normalized_type = (content_type or "").lower().strip()
    if normalized_type == "image/jpeg":
        return ".jpg"
    if normalized_type == "image/png":
        return ".png"
    if normalized_type == "image/gif":
        return ".gif"
    if normalized_type == "image/webp":
        return ".webp"
    if normalized_type == "image/svg+xml":
        return ".svg"
    guessed = mimetypes.guess_extension(normalized_type or "")
    if guessed:
        return guessed

    # -----------------------------------------------------------------------------
    # 2) URL 확장자 폴백
    # -----------------------------------------------------------------------------
    if isinstance(original_url, str) and "." in original_url:
        suffix = original_url.rsplit(".", 1)[-1].split("?", 1)[0].split("#", 1)[0]
        cleaned = suffix.strip().lower()
        if cleaned and 1 <= len(cleaned) <= 5:
            return f".{cleaned}"

    # -----------------------------------------------------------------------------
    # 3) 기본값
    # -----------------------------------------------------------------------------
    return ".bin"


def _parse_data_url(value: str) -> tuple[str, bytes] | None:
    """data URL(base64)에서 content_type과 데이터를 추출합니다."""

    match = DATA_URL_PATTERN.match(value or "")
    if not match:
        return None
    content_type = match.group("type").strip().lower()
    raw_data = match.group("data").strip()
    cleaned = re.sub(r"\s+", "", raw_data)
    try:
        decoded = base64.b64decode(cleaned)
    except Exception:
        logger.warning("Invalid base64 data URL detected")
        return None
    return content_type, decoded


def _rewrite_html_and_collect_assets(
    *,
    html: str,
    email_id: int,
    cid_map: dict[str, dict[str, Any]],
) -> tuple[str, list[EmailAssetPayload]]:
    """HTML을 재작성하고 이미지 자산 목록을 수집합니다.

    입력:
        html: 원본/정제된 HTML 문자열.
        email_id: Email 기본 키.
        cid_map: cid -> 이미지 데이터 매핑.
    주의:
        외부 URL(http/https)은 HTML을 변경하지 않고 OCR 대상만 수집합니다.
    반환:
        (재작성 HTML, EmailAssetPayload 리스트).
    부작용:
        없음.
    오류:
        HTML 파싱 실패 시 원문 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 파서 준비
    # -----------------------------------------------------------------------------
    if not html:
        return "", []
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return html, []

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        logger.exception("Failed to parse email HTML for asset extraction")
        return html, []
    assets: list[EmailAssetPayload] = []
    sequence = 0

    def register_asset(
        *,
        source: str,
        content_type: str | None,
        data: bytes | None,
        original_url: str | None,
    ) -> str:
        """자산을 등록하고 재작성 URL을 반환합니다."""

        nonlocal sequence
        sequence += 1
        assets.append(
            EmailAssetPayload(
                sequence=sequence,
                source=source,
                content_type=content_type,
                data=data,
                original_url=original_url,
            )
        )
        return _build_email_asset_url(email_id, sequence)

    def rewrite_url(raw_url: str) -> str:
        """URL 문자열을 분석해 필요 시 자산 URL로 치환합니다."""

        normalized = (raw_url or "").strip().strip("\"'")
        if not normalized:
            return raw_url

        lowered = normalized.lower()
        if lowered.startswith("cid:"):
            cid_key = normalized[4:].strip().strip("<>").strip()
            payload = cid_map.get(cid_key)
            if not payload:
                return raw_url
            data = payload.get("data")
            content_type = payload.get("content_type") or "image/png"
            if not data:
                return raw_url
            return register_asset(
                source=EmailAsset.Source.CID,
                content_type=str(content_type),
                data=data,
                original_url=None,
            )

        if lowered.startswith("data:"):
            parsed = _parse_data_url(normalized)
            if not parsed:
                return raw_url
            content_type, data = parsed
            return register_asset(
                source=EmailAsset.Source.DATA_URL,
                content_type=content_type,
                data=data,
                original_url=None,
            )

        if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("//"):
            register_asset(
                source=EmailAsset.Source.EXTERNAL_URL,
                content_type=None,
                data=None,
                original_url=normalized,
            )
            return raw_url

        return raw_url

    # -----------------------------------------------------------------------------
    # 2) img/src 처리
    # -----------------------------------------------------------------------------
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        img["src"] = rewrite_url(str(src))

    # -----------------------------------------------------------------------------
    # 3) srcset 처리
    # -----------------------------------------------------------------------------
    for tag in soup.find_all(srcset=True):
        raw_srcset = str(tag.get("srcset") or "")
        if not raw_srcset:
            continue
        rebuilt: list[str] = []
        for match in SRCSET_PATTERN.finditer(raw_srcset):
            url = match.group(1)
            descriptor = match.group(2) or ""
            if not url:
                continue
            rewritten = rewrite_url(url)
            rebuilt.append(f"{rewritten}{descriptor}")
        if rebuilt:
            tag["srcset"] = ", ".join(rebuilt)

    # -----------------------------------------------------------------------------
    # 4) style 속성의 url(...) 치환
    # -----------------------------------------------------------------------------
    for tag in soup.find_all(style=True):
        style_value = str(tag.get("style") or "")
        if not style_value:
            continue

        def replace_style_url(match: re.Match[str]) -> str:
            raw_value = match.group(1).strip().strip("\"'")
            if not raw_value:
                return match.group(0)
            rewritten = rewrite_url(raw_value)
            return f"url(\"{rewritten}\")"

        tag["style"] = CSS_URL_PATTERN.sub(replace_style_url, style_value)

    # -----------------------------------------------------------------------------
    # 5) <style> 태그의 url(...) 치환
    # -----------------------------------------------------------------------------
    for style_tag in soup.find_all("style"):
        raw_text = style_tag.string if style_tag.string is not None else style_tag.get_text()
        if not raw_text:
            continue

        def replace_block_url(match: re.Match[str]) -> str:
            raw_value = match.group(1).strip().strip("\"'")
            if not raw_value:
                return match.group(0)
            rewritten = rewrite_url(raw_value)
            return f"url(\"{rewritten}\")"

        updated = CSS_URL_PATTERN.sub(replace_block_url, raw_text)
        style_tag.string = updated

    # -----------------------------------------------------------------------------
    # 6) 결과 반환
    # -----------------------------------------------------------------------------
    return soup.prettify(), assets


def store_email_html_and_assets(
    *,
    email: Email,
    body_html: str | None,
    cid_map: dict[str, dict[str, Any]] | None,
) -> None:
    """HTML 본문과 이미지 자산을 MinIO에 저장하고 DB를 갱신합니다.

    입력:
        email: Email 인스턴스.
        body_html: HTML 문자열.
        cid_map: cid -> 이미지 데이터 매핑.
    반환:
        없음.
    부작용:
        - MinIO에 HTML/이미지 업로드
        - EmailAsset/Email 업데이트
    오류:
        MinIO/DB 오류가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증 및 중복 처리 방지
    # -----------------------------------------------------------------------------
    if not body_html:
        return
    if email.body_html_object_key:
        return

    # -----------------------------------------------------------------------------
    # 2) HTML 재작성 및 자산 수집
    # -----------------------------------------------------------------------------
    rewritten_html, assets = _rewrite_html_and_collect_assets(
        html=body_html,
        email_id=email.id,
        cid_map=cid_map or {},
    )

    # -----------------------------------------------------------------------------
    # 3) MinIO 업로드 준비 및 업로드
    # -----------------------------------------------------------------------------
    uploaded_keys: list[str] = []
    asset_rows: list[EmailAsset] = []
    try:
        for asset in assets:
            object_key = None
            byte_size = None
            if asset.data is not None:
                extension = _resolve_extension(
                    content_type=asset.content_type,
                    original_url=asset.original_url,
                )
                object_key = _build_email_asset_object_key(email.id, asset.sequence, extension)
                upload_bytes(
                    object_key=object_key,
                    data=asset.data,
                    content_type=asset.content_type,
                )
                uploaded_keys.append(object_key)
                byte_size = len(asset.data)

            asset_rows.append(
                EmailAsset(
                    email=email,
                    sequence=asset.sequence,
                    object_key=object_key,
                    content_type=asset.content_type,
                    byte_size=byte_size,
                    source=asset.source,
                    original_url=asset.original_url,
                )
            )

        html_key = _build_email_html_object_key(email.id)
        upload_bytes(
            object_key=html_key,
            data=rewritten_html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )
        uploaded_keys.append(html_key)

        # -------------------------------------------------------------------------
        # 4) DB 업데이트
        # -------------------------------------------------------------------------
        with transaction.atomic():
            if asset_rows:
                EmailAsset.objects.bulk_create(asset_rows)
            email.body_html_object_key = html_key
            email.save(update_fields=["body_html_object_key"])
    except Exception:
        logger.exception("Failed to store email HTML/assets (email_id=%s)", email.id)
        for key in uploaded_keys:
            try:
                delete_object(object_key=key)
            except Exception:
                logger.exception("Failed to rollback MinIO object: %s", key)
        raise


def load_email_html(*, email: Email) -> bytes | None:
    """Email HTML 오브젝트를 MinIO에서 읽어 반환합니다.

    입력:
        email: Email 인스턴스.
    반환:
        HTML 바이트 또는 None.
    부작용:
        MinIO GET 요청.
    오류:
        MinIO 오류가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 오브젝트 키 확인
    # -----------------------------------------------------------------------------
    object_key = getattr(email, "body_html_object_key", None)
    if not isinstance(object_key, str) or not object_key.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 다운로드 수행
    # -----------------------------------------------------------------------------
    return download_bytes(object_key=object_key.strip())


def load_email_asset(*, asset: EmailAsset) -> bytes | None:
    """EmailAsset 오브젝트를 MinIO에서 읽어 반환합니다.

    입력:
        asset: EmailAsset 인스턴스.
    반환:
        이미지 바이트 또는 None.
    부작용:
        MinIO GET 요청.
    오류:
        MinIO 오류가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 오브젝트 키 확인
    # -----------------------------------------------------------------------------
    object_key = getattr(asset, "object_key", None)
    if not isinstance(object_key, str) or not object_key.strip():
        return None

    # -----------------------------------------------------------------------------
    # 2) 다운로드 수행
    # -----------------------------------------------------------------------------
    return download_bytes(object_key=object_key.strip())


def delete_email_objects(*, html_key: str | None, asset_keys: Sequence[str]) -> None:
    """Email HTML/자산 오브젝트를 MinIO에서 삭제합니다.

    입력:
        html_key: HTML 오브젝트 키.
        asset_keys: 자산 오브젝트 키 목록.
    반환:
        없음.
    부작용:
        MinIO DELETE 요청.
    오류:
        MinIO 오류가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) 삭제 대상 구성
    # -----------------------------------------------------------------------------
    keys: list[str] = []
    if isinstance(html_key, str) and html_key.strip():
        keys.append(html_key.strip())
    for key in asset_keys:
        if isinstance(key, str) and key.strip():
            keys.append(key.strip())

    # -----------------------------------------------------------------------------
    # 2) 삭제 수행
    # -----------------------------------------------------------------------------
    for key in keys:
        delete_object(object_key=key)


__all__ = [
    "delete_email_objects",
    "load_email_asset",
    "load_email_html",
    "save_parsed_email",
    "store_email_html_and_assets",
]
