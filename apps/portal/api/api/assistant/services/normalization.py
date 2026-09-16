# =============================================================================
# 모듈: 어시스턴트 입력/응답 정규화
# 주요 함수: resolve_permission_groups, resolve_rag_index_names
# 주요 가정: permission_groups는 접근 가능한 그룹에 한해 허용합니다.
# =============================================================================
from __future__ import annotations

from typing import List, Sequence, Tuple

from api.account import selectors as account_selectors
import api.rag.services as rag_services

from .. import selectors
from .errors import AssistantRequestError
from .parsing import _normalize_string_list


def validate_user_identity(user: object) -> Tuple[str, str]:
    """사용자 객체에서 knox_id를 추출합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        (user_key, user_header_id) 튜플.

    부작용:
        없음. 순수 검증입니다.

    오류:
        knox_id가 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 추출 및 검증
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if not isinstance(knox_id, str) or not knox_id.strip():
        raise AssistantRequestError("knox_id가 필요합니다.")

    # -----------------------------------------------------------------------------
    # 2) 정규화된 키 반환
    # -----------------------------------------------------------------------------
    normalized = knox_id.strip()
    return normalized, normalized


def normalize_csv_string(raw: str) -> List[str]:
    """comma-separated 문자열을 리스트로 정규화합니다.

    인자:
        raw: 콤마로 구분된 문자열.

    반환:
        공백 제거 및 중복 제거된 문자열 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 빈 입력 처리
    # -----------------------------------------------------------------------------
    if not raw:
        return []
    # -----------------------------------------------------------------------------
    # 2) 분리/정리 후 중복 제거
    # -----------------------------------------------------------------------------
    normalized = [value.strip() for value in raw.split(",") if value.strip()]
    return list(dict.fromkeys(normalized))


def resolve_sender_id(user: object) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        sender_id 문자열 또는 None.

    부작용:
        없음. 순수 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 추출 및 정규화
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def default_permission_groups(user: object) -> List[str]:
    """기본 permission_groups 값을 계산합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        기본 권한 그룹 문자열 리스트.

    부작용:
        없음. 순수 계산입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 소속(user_sdwt_prod) 반영
    # -----------------------------------------------------------------------------
    allowed_mailboxes = selectors.get_accessible_email_user_sdwt_prods_for_user(
        user=user
    )
    groups: List[str] = []
    raw_user_sdwt = account_selectors.get_current_user_sdwt_prod(user=user)
    if (
        isinstance(raw_user_sdwt, str)
        and raw_user_sdwt.strip()
        and raw_user_sdwt.strip() in allowed_mailboxes
    ):
        groups.append(raw_user_sdwt.strip())

    # -----------------------------------------------------------------------------
    # 2) 발신자 ID + 공개 그룹 추가
    # -----------------------------------------------------------------------------
    sender_id = resolve_sender_id(user)
    if sender_id:
        groups.append(sender_id)
    groups.append(rag_services.RAG_PUBLIC_GROUP)
    return list(dict.fromkeys(groups))


def resolve_permission_groups(raw_groups: Sequence[object] | None, user: object) -> List[str]:
    """Tool 입력과 사용자 정보로 permission group을 결정합니다.

    인자:
        raw_groups: 표준 Turn Tool 입력의 permission group 배열.
        user: Django 사용자 객체.

    반환:
        접근 허용된 permission_groups 문자열 리스트.

    부작용:
        없음. 읽기 전용 검증입니다.

    오류:
        잘못된 타입이면 ValueError, 권한 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 표준 Tool 입력 검증
    # -----------------------------------------------------------------------------
    if raw_groups is not None and not isinstance(raw_groups, (list, tuple)):
        raise ValueError("permission_groups must be an array")

    # -----------------------------------------------------------------------------
    # 2) 기본 그룹 계산
    # -----------------------------------------------------------------------------
    normalized = _normalize_string_list(raw_groups)
    if not normalized:
        normalized = default_permission_groups(user)

    # -----------------------------------------------------------------------------
    # 3) 접근 가능 그룹 검증
    # -----------------------------------------------------------------------------
    accessible = selectors.get_accessible_email_user_sdwt_prods_for_user(user=user)
    allowed = set(accessible)
    sender_id = resolve_sender_id(user)
    if sender_id:
        allowed.add(sender_id)
    allowed.add(rag_services.RAG_PUBLIC_GROUP)
    invalid = [group for group in normalized if group not in allowed]
    if invalid:
        raise AssistantRequestError("해당 permission_groups에 대한 접근 권한이 없습니다.")

    return normalized


def resolve_rag_index_names(raw_indexes: Sequence[object] | None) -> List[str]:
    """표준 Turn Tool 입력으로 RAG 인덱스 목록을 결정합니다.

    인자:
        raw_indexes: 표준 Turn Tool 입력의 RAG 인덱스 배열.

    반환:
        유효한 RAG 인덱스 이름 리스트.

    부작용:
        없음. 읽기 전용 검증입니다.

    오류:
        입력 형식이 잘못되면 ValueError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 표준 Tool 입력 검증
    # -----------------------------------------------------------------------------
    if raw_indexes is None:
        normalized: List[str] = []
    elif isinstance(raw_indexes, (list, tuple)):
        normalized = _normalize_string_list(raw_indexes)
    else:
        raise ValueError("rag_indexes must be an array")

    # -----------------------------------------------------------------------------
    # 2) 설정에 등록된 기본 인덱스 적용
    # -----------------------------------------------------------------------------
    if not normalized:
        return rag_services.resolve_rag_index_names(None)

    # -----------------------------------------------------------------------------
    # 3) 후보군 검증
    # -----------------------------------------------------------------------------
    candidates = rag_services.get_rag_index_candidates()
    if candidates:
        invalid = [value for value in normalized if value not in candidates]
        if invalid:
            raise ValueError("rag_index_name contains invalid index")

    return normalized


def build_rag_index_list_payload(*, user: object) -> dict[str, object]:
    """현재 사용자 기준 RAG 인덱스/권한 그룹 정보를 반환합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        RAG 인덱스/권한 그룹/현재 사용자 정보를 포함한 dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        sender_id가 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 가능한 그룹 조회
    # -----------------------------------------------------------------------------
    accessible = selectors.get_accessible_email_user_sdwt_prods_for_user(user=user)
    current_user_sdwt_prod = account_selectors.get_current_user_sdwt_prod(user=user)
    permission_groups = set(accessible)
    if current_user_sdwt_prod not in accessible:
        current_user_sdwt_prod = ""

    # -----------------------------------------------------------------------------
    # 2) sender_id 검증 및 그룹 확장
    # -----------------------------------------------------------------------------
    sender_id = resolve_sender_id(user)
    if not sender_id:
        raise AssistantRequestError("forbidden")
    permission_groups.add(sender_id)
    permission_groups.add(rag_services.RAG_PUBLIC_GROUP)

    # -----------------------------------------------------------------------------
    # 3) 응답 payload 구성
    # -----------------------------------------------------------------------------
    return {
        "ragIndexes": rag_services.get_rag_index_candidates(),
        "defaultRagIndex": rag_services.resolve_rag_index_name(None),
        "emailRagIndex": rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        "permissionGroups": sorted(permission_groups),
        "currentUserSdwtProd": current_user_sdwt_prod,
        "ragPublicGroup": rag_services.RAG_PUBLIC_GROUP,
    }
