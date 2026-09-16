"""ct_process_comment 요약 상태와 응답 정규화 상수입니다."""

from __future__ import annotations

import re


SUMMARY_STATUS_SUCCESS = "success"
SUMMARY_STATUS_FAILED = "failed"
SUMMARY_STATUS_SKIPPED = "skipped"
SUMMARY_STATUS_DRY_RUN = "dry_run"
SUMMARY_STATUS_EXHAUSTED = "exhausted"
NO_CORE_SUMMARY_SENTINEL = "NO_CORE_SUMMARY"
SUMMARY_MAX_RETRY_COUNT = 3
SUMMARY_LAST_ERROR_MAX_CHARS = 8000
SUMMARY_SECTION_PREFIX_PATTERN = re.compile(r"^(원인|조치사항|결과)\s*:")
SUMMARY_TIME_LINE_PATTERN = re.compile(
    r"^(?P<time>(?:\d{4}[-/.]\d{2}[-/.]\d{2}\s+)?\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<event>.+)$"
)
CORE_SUMMARY_REWRITE_PREFIX = "REWRITE:"
OPENWEBUI_DIAGNOSTIC_VERSION = "ctpc-openwebui-v3"
OPENWEBUI_SAFE_RESPONSE_HEADERS = (
    "Content-Type",
    "Content-Length",
    "Transfer-Encoding",
    "Server",
    "Via",
    "X-Request-ID",
    "X-OpenAI-Request-ID",
    "X-Correlation-ID",
    "Traceparent",
    "CF-Ray",
    "X-Envoy-Upstream-Service-Time",
)
