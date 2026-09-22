# =============================================================================
# 모듈 설명: Emails 자산·OCR 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from django.db.models import Q, QuerySet

from ..models import EmailAsset

def get_email_asset_by_id(*, asset_id: int) -> EmailAsset | None:
    """asset_id로 EmailAsset을 조회하고 없으면 None을 반환합니다.

    입력:
        asset_id: EmailAsset 기본 키.
    반환:
        EmailAsset 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not isinstance(asset_id, int):
        return None

    # -----------------------------------------------------------------------------
    # 2) 조회 수행
    # -----------------------------------------------------------------------------
    try:
        return EmailAsset.objects.get(id=asset_id)
    except EmailAsset.DoesNotExist:
        return None


def get_email_asset_by_email_and_sequence(*, email_id: int, sequence: int) -> EmailAsset | None:
    """email_id/sequence로 EmailAsset을 조회하고 없으면 None을 반환합니다.

    입력:
        email_id: Email 기본 키.
        sequence: 이미지 순번.
    반환:
        EmailAsset 인스턴스 또는 None.
    부작용:
        없음. 조회 전용.
    오류:
        없으면 None 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int) or not isinstance(sequence, int):
        return None

    # -----------------------------------------------------------------------------
    # 2) 조회 수행
    # -----------------------------------------------------------------------------
    try:
        return EmailAsset.objects.get(email_id=email_id, sequence=sequence)
    except EmailAsset.DoesNotExist:
        return None


def list_email_assets_by_email_ids(*, email_ids: Sequence[int]) -> QuerySet[EmailAsset]:
    """Email id 목록에 해당하는 EmailAsset QuerySet을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        EmailAsset QuerySet(조회 결과).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not email_ids:
        return EmailAsset.objects.none()
    normalized = [int(value) for value in email_ids if isinstance(value, int) or str(value).isdigit()]
    if not normalized:
        return EmailAsset.objects.none()

    # -----------------------------------------------------------------------------
    # 2) QuerySet 반환
    # -----------------------------------------------------------------------------
    return EmailAsset.objects.filter(email_id__in=normalized).order_by("email_id", "sequence")


def list_claimable_email_assets(
    *,
    now: datetime,
    max_attempts: int,
) -> QuerySet[EmailAsset]:
    """OCR 처리 대상 EmailAsset QuerySet을 반환합니다.

    입력:
        now: 기준 시각(락 만료 판단용).
        max_attempts: 최대 시도 횟수.
    반환:
        OCR 처리 대상 EmailAsset QuerySet.
    부작용:
        없음. 조회 전용.
    오류:
        입력이 잘못되면 빈 QuerySet 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(now, datetime):
        return EmailAsset.objects.none()
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        return EmailAsset.objects.none()

    # -----------------------------------------------------------------------------
    # 2) OCR 처리 대상 필터 구성
    # -----------------------------------------------------------------------------
    return (
        EmailAsset.objects.filter(
            Q(ocr_status=EmailAsset.OcrStatus.PENDING)
            | Q(ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__lt=max_attempts)
            | Q(ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__isnull=True)
            | Q(ocr_status=EmailAsset.OcrStatus.PROCESSING, ocr_lock_expires_at__lte=now)
            | Q(ocr_status=EmailAsset.OcrStatus.PROCESSING, ocr_lock_expires_at__isnull=True)
        )
        .order_by("id")
    )


def list_claimable_email_assets_for_update(
    *,
    now: datetime,
    max_attempts: int,
    limit: int,
) -> list[EmailAsset]:
    """OCR 처리 대상 EmailAsset을 행 잠금으로 조회해 반환합니다.

    입력:
        now: 기준 시각(락 만료 판단용).
        max_attempts: 최대 시도 횟수.
        limit: 최대 조회 개수.
    반환:
        EmailAsset 인스턴스 리스트.
    부작용:
        없음. 호출 측 트랜잭션에서 행 잠금이 발생합니다.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) limit 검증
    # -----------------------------------------------------------------------------
    if not isinstance(limit, int) or limit <= 0:
        return []

    # -----------------------------------------------------------------------------
    # 2) 행 잠금 조회
    # -----------------------------------------------------------------------------
    queryset = list_claimable_email_assets(now=now, max_attempts=max_attempts)
    return list(queryset.select_for_update(skip_locked=True)[:limit])


def list_email_asset_keys_by_email_ids(*, email_ids: Sequence[int]) -> list[str]:
    """Email id 목록에 연결된 EmailAsset object_key 목록을 반환합니다.

    입력:
        email_ids: Email id 목록.
    반환:
        object_key 문자열 리스트(빈 값 제외).
    부작용:
        없음. 조회 전용.
    오류:
        email_ids가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) QuerySet 조회
    # -----------------------------------------------------------------------------
    assets = list_email_assets_by_email_ids(email_ids=email_ids)

    # -----------------------------------------------------------------------------
    # 2) 키 목록 구성
    # -----------------------------------------------------------------------------
    keys = [row.object_key for row in assets if isinstance(row.object_key, str) and row.object_key.strip()]
    return keys


def build_email_ocr_text(*, email_id: int) -> str:
    """이메일에 연결된 OCR 텍스트를 sequence 순서로 합쳐 반환합니다.

    입력:
        email_id: Email 기본 키.
    반환:
        결합된 OCR 텍스트(없으면 빈 문자열).
    부작용:
        없음. 조회 전용.
    오류:
        email_id가 유효하지 않으면 빈 문자열 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int):
        return ""

    # -----------------------------------------------------------------------------
    # 2) OCR 텍스트 조회
    # -----------------------------------------------------------------------------
    rows = (
        EmailAsset.objects.filter(email_id=email_id, ocr_status=EmailAsset.OcrStatus.DONE)
        .exclude(ocr_text="")
        .order_by("sequence")
        .values_list("ocr_text", flat=True)
    )

    # -----------------------------------------------------------------------------
    # 3) 결합 결과 반환
    # -----------------------------------------------------------------------------
    return "\n".join([text for text in rows if text])


def has_unprocessed_email_assets(*, email_id: int, max_attempts: int) -> bool:
    """해당 Email에 OCR 미처리 자산이 존재하는지 확인합니다.

    입력:
        email_id: Email 기본 키.
        max_attempts: 최대 시도 횟수.
    반환:
        미처리 자산이 있으면 True.
    부작용:
        없음. 조회 전용.
    오류:
        입력이 유효하지 않으면 False 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(email_id, int):
        return False
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        return False

    # -----------------------------------------------------------------------------
    # 2) 처리 완료 조건 구성
    # -----------------------------------------------------------------------------
    done_or_exhausted = Q(ocr_status=EmailAsset.OcrStatus.DONE) | Q(
        ocr_status=EmailAsset.OcrStatus.FAILED, ocr_attempt_count__gte=max_attempts
    )

    # -----------------------------------------------------------------------------
    # 3) 미처리 자산 존재 여부 확인
    # -----------------------------------------------------------------------------
    return EmailAsset.objects.filter(email_id=email_id).exclude(done_or_exhausted).exists()
