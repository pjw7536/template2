# =============================================================================
# 모듈 설명: 공용 상수/정규식을 제공합니다.
# - 주요 대상: SAFE_IDENTIFIER, DATE_ONLY_REGEX, DEFAULT_TABLE 등
# - 불변 조건: 상수만 정의하며 런타임 로직을 포함하지 않습니다.
# =============================================================================

"""뷰 전역에서 공유하는 상수 정의.

- 주요 대상: 정규식, 기본 테이블명, 컬럼 후보 목록
- 주요 엔드포인트/클래스: 없음(상수만 제공)
- 가정/불변 조건: 날짜 문자열은 YYYY-MM-DD, 식별자는 SAFE_IDENTIFIER 규칙 준수
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 정규식 및 기본 테이블 설정
# ---------------------------------------------------------------------------
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")  # 안전한 식별자(테이블/컬럼) 검증
DATE_ONLY_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD 형식 검증
DATE_COLUMN_CANDIDATES = [
    "created_at",
    "updated_at",
    "timestamp",
    "ts",
    "date",
]  # 베이스 타임스탬프 후보

DEFAULT_TABLE = "drone_sop"
LINE_SDWT_TABLE_NAME = "account_affiliation"
DIMENSION_CANDIDATES = [
    "sdwt_prod",
    "proc_id",
    "ppid",
    "user_sdwt_prod",
    "eqp_id",
    "main_step",
    "sample_type",
    "line_id",
]

MAX_FIELD_LENGTH = 50
