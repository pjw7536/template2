"""뷰 전역에서 공유하는 상수 정의."""
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

DEFAULT_TABLE = "drone_sop_v3"
LINE_SDWT_TABLE_NAME = "line_sdwt"
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
