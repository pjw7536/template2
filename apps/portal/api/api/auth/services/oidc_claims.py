# =============================================================================
# 모듈 설명: OIDC 클레임을 사용자 정보로 변환하고 저장합니다.
# - 주요 대상: 클레임 매핑, 사용자 생성/갱신
# - 불변 조건: userid(EPID)는 사용자 식별 기준이며 sabun과 loginid도 필수입니다.
# =============================================================================

"""OIDC 클레임 기반 사용자 생성/갱신 서비스.

- 주요 대상: 클레임 필드 매핑, 사용자 upsert
- 주요 함수: extract_user_info_from_claims, upsert_user_from_claims
- 가정/불변 조건: EPID로만 사용자를 조회하고 knox_id는 비어 있을 수 없음
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import api.account.services as account_services


def extract_user_info_from_claims(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Keycloak 클레임을 사용자 모델 필드로 매핑해 반환합니다.

    입력:
    - claims: id_token에서 추출한 클레임 딕셔너리

    반환:
    - Dict[str, Any]: 사용자 필드 매핑 결과

    부작용:
    - 없음

    오류:
    - 없음
    """
    claim_to_field = {
        "loginid": "knox_id",
        "userid": "avatarid",
        "sabun": "sabun",
        "username": "username",
        "username_en": "username_en",
        "first_name": "first_name",
        "last_name": "last_name",
        "givenname": "givenname",
        "surname": "surname",
        "deptname": "department",
        "deptid": "deptid",
        "mail": "email",
        "grdName": "grd_name",
        "grdname_en": "grdname_en",
        "busname": "busname",
        "intcode": "intcode",
        "intname": "intname",
        "origincomp": "origincomp",
        "employeetype": "employeetype",
    }

    info: Dict[str, Any] = {}
    for claim_key, field_name in claim_to_field.items():
        raw = claims.get(claim_key)
        if raw is not None and not isinstance(raw, str):
            raise ValueError("invalid_identity_claims")
        value = raw.strip() if raw is not None else ""
        info[field_name] = value or None

    # Keycloak 표준 claim은 사내 legacy claim이 없을 때만 fallback으로 사용합니다.
    standard_fallbacks = {
        "username": "name",
        "first_name": "given_name",
        "last_name": "family_name",
        "email": "email",
    }
    for field_name, claim_key in standard_fallbacks.items():
        if info.get(field_name):
            continue
        raw = claims.get(claim_key)
        if raw is not None and not isinstance(raw, str):
            raise ValueError("invalid_identity_claims")
        value = raw.strip() if raw is not None else ""
        info[field_name] = value or None

    # 한글 username만 있는 기존 SSO 응답에서도 first_name/last_name을 유지합니다.
    username = info.get("username") or ""
    if username and (not info.get("first_name") or not info.get("last_name")):
        trimmed = username.strip()
        if trimmed:
            if len(trimmed) >= 2:
                info["last_name"] = info.get("last_name") or trimmed[:1]
                info["first_name"] = info.get("first_name") or trimmed[1:]
            else:
                info["first_name"] = info.get("first_name") or trimmed

    info["identity_profile"] = {key: claims.get(key, "") for key in ("user_sdwt_prod", "line_id")}
    return info


def upsert_user_from_claims(
    *,
    info: Dict[str, Any],
    sabun: str,
    knox_id: str,
) -> tuple[Any, bool]:
    """클레임 정보 기반으로 사용자를 생성/갱신합니다.

    입력:
    - info: 클레임에서 추출한 사용자 정보
    - sabun: 사번 문자열
    - knox_id: 로그인 ID 문자열

    반환:
    - tuple[Any, bool]: (사용자 객체, 생성 여부)

    부작용:
    - 사용자 생성/갱신

    오류:
    - IntegrityError: 사용자 생성 경합 발생 시 재시도 후에도 실패
    """
    return account_services.upsert_user_identity(
        identity=info,
        sabun=sabun,
        knox_id=knox_id,
    )


__all__ = [
    "extract_user_info_from_claims",
    "upsert_user_from_claims",
]
