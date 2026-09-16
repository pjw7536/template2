"""L3 Spider 서비스 모듈이 공유하는 상수와 cache 상태입니다."""

from __future__ import annotations

from .analytics import ANOMALY_STATUSES
from .cache import TTLCache

SUMMARY_COLUMNS = ["step_seq", "ppid", "eqp_id", "eqc", "bin_name", "display_status"]
# 파일명에서 step_seq/ppid 파싱 성공 시 파일에서 읽을 컬럼 (절반으로 감소)
_SUMMARY_COLUMNS_SLIM = ["eqc", "bin_name", "display_status"]
_SUMMARY_DEDUP_KEYS = ["step_seq", "ppid", "eqc", "bin_name", "display_status"]
# daily summary: 카운트 집계용 — dedup 없이 전체 행을 읽습니다.
_DAILY_SUMMARY_COLUMNS = ["step_seq", "ppid", "eqc", "bin_name", "display_status", "lot_id"]
_DAILY_SUMMARY_COLUMNS_SLIM = ["step_seq", "eqc", "bin_name", "display_status", "lot_id"]
_STATS_COLUMNS = ["eqc", "bin_name", "display_status", "tkin_time"]
MAIL_EVENT_COLUMNS = ["step_seq", "ppid", "eqc", "bin_name", "display_status", "tkin_time"]
CHART_COLUMNS = [
    "tkin_time",
    "tkout_time",
    "owning",
    "step_seq",
    "ppid",
    "root_lot_id",
    "lot_id",
    "wafer_id",
    "eqp_id",
    "chamber_id",
    "eqc",
    "bin_name",
    "bin_value",
    "prop_over_50",
    "q1",
    "q3",
    "iqr",
    "lsl",
    "usl",
    "seq_idx",
    "risk_score",
    "display_status",
    "comment",
]
MAIL_SEVERITY_STATUSES = {
    "high_risk": {"High Risk Chamber"},
    "warning_or_high_risk": ANOMALY_STATUSES,
}
_MAX_PARALLEL_WORKERS = 8
_MAIL_DIGEST_PREVIEW_LIMIT = 50
_MetaCombo = tuple[str, str, str, str, str]


_meta_cache = TTLCache(ttl=600.0)
_structure_cache = TTLCache(ttl=600.0)
_stats_cache = TTLCache(ttl=600.0)
_daily_summary_cache = TTLCache(ttl=300.0)
# Meta 원본 조합을 따로 캐싱해 사용자별 exclusion 규칙과 분리하고,
# 같은 워커의 여러 사용자가 PostgreSQL 조회 비용을 공유합니다.
_meta_combos_cache = TTLCache(ttl=600.0)
_completed_dates_cache = TTLCache(ttl=600.0)
_COMPLETED_DATES_KEY = "dates"
_line_groups_cache = TTLCache(ttl=600.0)
_line_rule_candidates_cache = TTLCache(ttl=300.0)
_LINE_RULE_CANDIDATES_KEY = "candidates"


class L3SpiderServiceError(Exception):
    """L3 Spider 서비스 오류를 HTTP 상태와 함께 표현합니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
