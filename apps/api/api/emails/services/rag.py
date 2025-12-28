# =============================================================================
# 모듈 설명: 이메일 RAG 인덱싱/삭제 요청을 처리합니다.
# - 주요 함수: enqueue_rag_index_for_emails, register_email_to_rag, process_email_outbox_batch
# - 불변 조건: RAG 작업은 Outbox를 통해 재시도하며, UNASSIGNED는 인덱싱하지 않습니다.
# =============================================================================

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Sequence

from django.db import transaction
from django.utils import timezone

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.rag import services as rag_services

from ..models import Email, EmailOutbox
from ..selectors import (
    list_emails_by_ids,
    list_pending_email_outbox,
    list_pending_rag_emails,
)

# =============================================================================
# 로깅
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 상수
# =============================================================================
OUTBOX_MAX_RETRIES = 5
OUTBOX_RETRY_BASE_SECONDS = 30
OUTBOX_RETRY_MAX_SECONDS = 3600


def _compute_outbox_backoff_seconds(retry_count: int) -> int:
    """재시도 횟수에 따른 백오프(초)를 계산합니다.

    입력:
        retry_count: 현재 재시도 횟수.
    반환:
        백오프 대기 시간(초).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 기본값 및 지수 백오프 계산
    # -----------------------------------------------------------------------------
    if retry_count <= 0:
        return OUTBOX_RETRY_BASE_SECONDS
    seconds = OUTBOX_RETRY_BASE_SECONDS * (2**retry_count)
    return min(seconds, OUTBOX_RETRY_MAX_SECONDS)


def _ensure_email_rag_doc_id(email: Email) -> None:
    """Email.rag_doc_id가 비어있으면 기본 규칙으로 채웁니다.

    입력:
        email: Email 인스턴스.
    반환:
        없음.
    부작용:
        rag_doc_id가 없으면 DB 업데이트 수행.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) doc_id 확인 및 생성
    # -----------------------------------------------------------------------------
    if email.rag_doc_id:
        return
    email.rag_doc_id = f"email-{email.id}"
    email.save(update_fields=["rag_doc_id"])


def _resolve_email_permission_groups(email: Email) -> list[str] | None:
    """이메일의 권한 그룹 목록을 계산합니다.

    입력:
        email: Email 인스턴스.
    반환:
        permission_groups 리스트(없으면 공개 그룹).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) user_sdwt_prod/sender_id 수집
    # -----------------------------------------------------------------------------
    user_sdwt_prod = (email.user_sdwt_prod or "").strip()
    sender_id = (email.sender_id or "").strip()
    groups: list[str] = []
    if user_sdwt_prod:
        groups.append(user_sdwt_prod)
    if sender_id:
        groups.append(sender_id)

    # -----------------------------------------------------------------------------
    # 2) 중복 제거 및 기본 그룹 처리
    # -----------------------------------------------------------------------------
    if groups:
        return list(dict.fromkeys(groups))
    return [rag_services.RAG_PUBLIC_GROUP]


def enqueue_email_outbox(
    *,
    email: Email | None,
    action: str,
    payload: dict[str, Any] | None = None,
) -> EmailOutbox:
    """이메일 RAG 작업을 Outbox로 적재합니다.

    입력:
        email: Email 인스턴스 또는 None.
        action: Outbox 액션 문자열.
        payload: 추가 데이터.
    반환:
        생성된 EmailOutbox 인스턴스.
    부작용:
        EmailOutbox 레코드 생성.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    return EmailOutbox.objects.create(
        email=email,
        action=action,
        payload=payload or {},
        status=EmailOutbox.Status.PENDING,
        available_at=timezone.now(),
    )


def enqueue_rag_index(*, email: Email, previous_user_sdwt_prod: str | None = None) -> EmailOutbox:
    """RAG 인덱싱 요청을 Outbox에 적재합니다.

    입력:
        email: Email 인스턴스.
        previous_user_sdwt_prod: 이전 메일함 식별자(있으면 포함).
    반환:
        생성된 EmailOutbox 인스턴스.
    부작용:
        EmailOutbox 레코드 생성.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) rag_doc_id 보장 및 payload 구성
    # -----------------------------------------------------------------------------
    _ensure_email_rag_doc_id(email)
    payload = {}
    if previous_user_sdwt_prod is not None:
        payload["previous_user_sdwt_prod"] = previous_user_sdwt_prod
    return enqueue_email_outbox(email=email, action=EmailOutbox.Action.INDEX, payload=payload)


def enqueue_rag_delete(*, email: Email) -> EmailOutbox | None:
    """RAG 삭제 요청을 Outbox에 적재합니다.

    입력:
        email: Email 인스턴스.
    반환:
        EmailOutbox 인스턴스 또는 None(rag_doc_id 없을 때).
    부작용:
        EmailOutbox 레코드 생성.
    오류:
        ORM 예외가 발생할 수 있음.
    """

    # -----------------------------------------------------------------------------
    # 1) rag_doc_id 확인
    # -----------------------------------------------------------------------------
    if not email.rag_doc_id:
        return None

    # -----------------------------------------------------------------------------
    # 2) payload 구성 및 Outbox 적재
    # -----------------------------------------------------------------------------
    permission_groups = _resolve_email_permission_groups(email)
    payload = {
        "rag_doc_id": email.rag_doc_id,
        "index_name": rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        "permission_groups": permission_groups,
    }
    return enqueue_email_outbox(email=email, action=EmailOutbox.Action.DELETE, payload=payload)


def _call_insert_email_to_rag(
    email: Email,
    *,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    """이메일을 RAG에 등록하는 실제 호출을 래핑합니다.

    입력:
        email: Email 인스턴스.
        index_name: RAG 인덱스 이름.
        permission_groups: 접근 권한 그룹.
    반환:
        없음.
    부작용:
        외부 RAG 서비스 호출.
    오류:
        RAG 서비스 오류가 발생할 수 있음.
    """

    from api.emails import services as email_services

    email_services.insert_email_to_rag(
        email,
        index_name=index_name,
        permission_groups=permission_groups,
    )


def _call_delete_rag_doc(
    doc_id: str,
    *,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    """RAG 문서 삭제 호출을 래핑합니다.

    입력:
        doc_id: RAG 문서 ID.
        index_name: RAG 인덱스 이름.
        permission_groups: 접근 권한 그룹.
    반환:
        없음.
    부작용:
        외부 RAG 서비스 호출.
    오류:
        RAG 서비스 오류가 발생할 수 있음.
    """

    from api.emails import services as email_services

    email_services.delete_rag_doc(
        doc_id,
        index_name=index_name,
        permission_groups=permission_groups,
    )


def enqueue_rag_index_for_emails(
    *,
    email_ids: list[int],
    target_user_sdwt_prod: str,
    previous_user_sdwt_prod_by_email_id: Dict[int, str | None] | None,
) -> Dict[str, int]:
    """메일 목록의 RAG 인덱싱을 즉시 시도하고 실패 시 Outbox에 적재합니다.

    입력:
        email_ids: 대상 Email id 목록.
        target_user_sdwt_prod: 이동 대상 메일함 식별자.
        previous_user_sdwt_prod_by_email_id: 이전 메일함 매핑.
    반환:
        ragRegistered/ragFailed/ragMissing 카운트 dict.
    부작용:
        - RAG 서비스 호출
        - 실패 시 Outbox 적재
    오류:
        개별 처리 오류는 로깅 후 다음 항목으로 진행.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not email_ids:
        return {"ragRegistered": 0, "ragFailed": 0, "ragMissing": 0}

    requested_ids = [
        int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()
    ]
    requested_set = set(requested_ids)
    resolved_ids: list[int] = []
    rag_registered = 0
    rag_failed = 0

    # -----------------------------------------------------------------------------
    # 2) 메일 조회 및 RAG 등록 시도
    # -----------------------------------------------------------------------------
    for email in list_emails_by_ids(email_ids=requested_ids).iterator():
        resolved_ids.append(email.id)
        previous_user_sdwt_prod = (
            previous_user_sdwt_prod_by_email_id.get(email.id)
            if previous_user_sdwt_prod_by_email_id is not None
            else None
        )
        try:
            register_email_to_rag(email, previous_user_sdwt_prod=previous_user_sdwt_prod)
            rag_registered += 1
        except Exception:
            logger.exception("Failed to register email to RAG id=%s", email.id)
            try:
                enqueue_rag_index(email=email, previous_user_sdwt_prod=previous_user_sdwt_prod)
            except Exception:
                logger.exception("Failed to enqueue RAG outbox for email id=%s", email.id)
                rag_failed += 1

    # -----------------------------------------------------------------------------
    # 3) 누락/결과 집계
    # -----------------------------------------------------------------------------
    resolved_set = set(resolved_ids)
    rag_missing = len(requested_set - resolved_set)

    return {"ragRegistered": rag_registered, "ragFailed": rag_failed, "ragMissing": rag_missing}


def register_email_to_rag(
    email: Email,
    previous_user_sdwt_prod: str | None = None,
    persist_fields: Sequence[str] | None = None,
) -> Email:
    """
    이메일을 RAG에 등록하고 rag_doc_id를 저장합니다.

    입력:
        email: Email 인스턴스.
        previous_user_sdwt_prod: 이전 메일함 식별자(옵션).
        persist_fields: 추가로 저장할 필드 목록(옵션).
    반환:
        갱신된 Email 인스턴스.
    부작용:
        - RAG 서비스 호출
        - Email 필드 업데이트
    오류:
        - 분류 상태/메일함 조건 미충족 시 ValueError
    """

    # -----------------------------------------------------------------------------
    # 1) 사전 검증 및 필드 보정
    # -----------------------------------------------------------------------------
    update_fields = []
    if email.classification_source != Email.ClassificationSource.CONFIRMED_USER:
        raise ValueError("Cannot register a non-confirmed email to RAG")

    normalized_user_sdwt = (email.user_sdwt_prod or "").strip()
    if not normalized_user_sdwt or normalized_user_sdwt == UNASSIGNED_USER_SDWT_PROD:
        raise ValueError("Cannot register an UNASSIGNED email to RAG")
    if normalized_user_sdwt != email.user_sdwt_prod:
        email.user_sdwt_prod = normalized_user_sdwt
        update_fields.append("user_sdwt_prod")
    if not email.rag_doc_id:
        email.rag_doc_id = f"email-{email.id}"
        update_fields.append("rag_doc_id")

    # -----------------------------------------------------------------------------
    # 2) RAG 등록 및 상태 업데이트
    # -----------------------------------------------------------------------------
    permission_groups = _resolve_email_permission_groups(email)
    target_index = rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS)
    _call_insert_email_to_rag(email, index_name=target_index, permission_groups=permission_groups)
    if email.rag_index_status != Email.RagIndexStatus.INDEXED:
        email.rag_index_status = Email.RagIndexStatus.INDEXED
        update_fields.append("rag_index_status")
    if persist_fields:
        update_fields.extend(list(persist_fields))
    if update_fields:
        email.save(update_fields=list(dict.fromkeys(update_fields)))  # 중복 제거
    return email


def _process_outbox_item(item: EmailOutbox) -> None:
    """단일 Outbox 항목을 처리합니다.

    입력:
        item: EmailOutbox 인스턴스.
    반환:
        없음.
    부작용:
        RAG 서비스 호출 및 Email 업데이트.
    오류:
        지원하지 않는 action이면 ValueError.
    """

    # -----------------------------------------------------------------------------
    # 1) 인덱싱 처리
    # -----------------------------------------------------------------------------
    if item.action == EmailOutbox.Action.INDEX:
        if item.email is None:
            raise ValueError("Email not found for outbox item")
        previous_user_sdwt_prod = item.payload.get("previous_user_sdwt_prod")
        register_email_to_rag(item.email, previous_user_sdwt_prod=previous_user_sdwt_prod)
        return

    # -----------------------------------------------------------------------------
    # 2) 삭제 처리
    # -----------------------------------------------------------------------------
    if item.action == EmailOutbox.Action.DELETE:
        rag_doc_id = item.payload.get("rag_doc_id")
        index_name = item.payload.get("index_name")
        permission_groups = item.payload.get("permission_groups")
        if not rag_doc_id or not index_name:
            raise ValueError("rag_doc_id or index_name missing for delete outbox item")
        _call_delete_rag_doc(rag_doc_id, index_name=index_name, permission_groups=permission_groups)
        return

    # -----------------------------------------------------------------------------
    # 3) 사용 중지된 액션 처리
    # -----------------------------------------------------------------------------
    if item.action in {EmailOutbox.Action.RECLASSIFY, EmailOutbox.Action.RECLASSIFY_ALL}:
        logger.info("Skipping deprecated outbox action=%s id=%s", item.action, item.id)
        return

    # -----------------------------------------------------------------------------
    # 4) 미지원 액션 처리
    # -----------------------------------------------------------------------------
    raise ValueError(f"Unsupported outbox action: {item.action}")


def process_email_outbox_batch(*, limit: int = 100) -> Dict[str, int]:
    """Outbox 항목을 처리하고 결과 통계를 반환합니다.

    입력:
        limit: 한 번에 처리할 최대 건수.
    반환:
        {"processed": 처리건수, "succeeded": 성공건수, "failed": 실패건수}
    부작용:
        EmailOutbox 상태 업데이트 및 RAG 호출.
    오류:
        처리 중 오류는 항목별로 실패 처리.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if limit <= 0:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    # -----------------------------------------------------------------------------
    # 2) 대기 항목 잠금/상태 변경
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        pending = list_pending_email_outbox(limit=limit, for_update=True)
        if not pending:
            return {"processed": 0, "succeeded": 0, "failed": 0}
        EmailOutbox.objects.filter(id__in=[item.id for item in pending]).update(
            status=EmailOutbox.Status.PROCESSING,
        )

    # -----------------------------------------------------------------------------
    # 3) 항목 처리 및 재시도 정책 적용
    # -----------------------------------------------------------------------------
    succeeded = 0
    failed = 0
    for item in pending:
        try:
            _process_outbox_item(item)
            EmailOutbox.objects.filter(id=item.id).update(
                status=EmailOutbox.Status.DONE,
                last_error="",
            )
            succeeded += 1
        except Exception as exc:
            logger.exception("Failed to process email outbox item id=%s", item.id)
            retry_count = item.retry_count + 1
            if retry_count >= OUTBOX_MAX_RETRIES:
                EmailOutbox.objects.filter(id=item.id).update(
                    status=EmailOutbox.Status.FAILED,
                    retry_count=retry_count,
                    last_error=str(exc),
                )
            else:
                delay = _compute_outbox_backoff_seconds(retry_count)
                EmailOutbox.objects.filter(id=item.id).update(
                    status=EmailOutbox.Status.PENDING,
                    retry_count=retry_count,
                    last_error=str(exc),
                    available_at=timezone.now() + timedelta(seconds=delay),
                )
            failed += 1

    # -----------------------------------------------------------------------------
    # 4) 결과 반환
    # -----------------------------------------------------------------------------
    return {"processed": len(pending), "succeeded": succeeded, "failed": failed}


def register_missing_rag_docs(limit: int = 500) -> int:
    """
    rag_doc_id가 없는 이메일을 Outbox에 적재합니다.

    입력:
        limit: 최대 처리 건수.
    반환:
        Outbox 적재 건수.
    부작용:
        EmailOutbox 레코드 생성.
    오류:
        개별 적재 실패는 로깅 후 계속 진행.
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 메일 조회
    # -----------------------------------------------------------------------------
    pending = list_pending_rag_emails(limit=limit)
    enqueued = 0

    # -----------------------------------------------------------------------------
    # 2) Outbox 적재
    # -----------------------------------------------------------------------------
    for email in pending:
        try:
            enqueue_rag_index(email=email)
            enqueued += 1
        except Exception:
            logger.exception("Failed to enqueue RAG outbox for email id=%s", email.id)

    return enqueued
