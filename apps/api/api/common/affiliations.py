# =============================================================================
# 모듈 설명: 소속(affiliation) 관련 공용 상수를 제공합니다.
# - 주요 대상: UNKNOWN, UNASSIGNED_USER_SDWT_PROD, UNCLASSIFIED_USER_SDWT_PROD
# - 불변 조건: 레거시 호환을 위해 UNCLASSIFIED 별칭을 유지합니다.
# =============================================================================

"""소속(affiliation) 관련 공용 상수 모음.

- 주요 대상: UNKNOWN, UNASSIGNED_USER_SDWT_PROD, UNCLASSIFIED_USER_SDWT_PROD
- 주요 엔드포인트/클래스: 없음(상수만 제공)
- 가정/불변 조건: 레거시 호환을 위해 UNCLASSIFIED 별칭을 유지함
"""
from __future__ import annotations

UNKNOWN = "UNKNOWN"
UNASSIGNED_USER_SDWT_PROD = "UNASSIGNED"
# 레거시 명칭과의 호환을 위한 별칭
UNCLASSIFIED_USER_SDWT_PROD = UNASSIGNED_USER_SDWT_PROD


__all__ = ["UNKNOWN", "UNASSIGNED_USER_SDWT_PROD", "UNCLASSIFIED_USER_SDWT_PROD"]
