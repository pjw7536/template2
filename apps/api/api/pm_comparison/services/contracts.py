"""PM Comparison 서비스의 공통 컬럼과 오류 계약입니다."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd

from api.pm_comparison import selectors

DATE_COLUMN = "날짜"

TRACE_COLUMNS = [
    "line_id",
    "eqp_id",
    "fdc_bin",
    "type",
    "ppid",
    "recipe_id",
    "trace_param_name",
    DATE_COLUMN,
    "root_lot_id",
    "lot_id",
    "wafer_id",
    "time",
    "step_time",
    "value",
    "ch_step",
    "slot_no",
    "group",
]

OES_ID_COLUMNS = [
    "line_id",
    "device_id",
    "ppid",
    "recipe_id",
    "step_seq",
    "eqp_id",
    "bin_id",
    "lot_id",
    "slot_id",
    DATE_COLUMN,
    "wafer_end_time",
    "rcp_step",
    "name",
    "Time",
    "wavelength",
    "value",
]
OES_DETAIL_METADATA_COLUMNS = list(
    dict.fromkeys(
        [
            *OES_ID_COLUMNS,
            "traj_phase",
            "phase",
            "cycle_index",
            "pm_date",
            "slot_no",
            "group",
        ]
    )
)

SCORE_COLUMNS = [
    "line_id",
    "eqp_id",
    "chamber_id",
    DATE_COLUMN,
    "type",
    "data_type",
    "item_name",
    "step",
    "wavelength",
    "score",
    # trace 전용 변화량 컬럼입니다.
    "delta_shape",
    "delta_jitter",
    "delta_level",
    "flag",
    "alarm_pct",
    # OES 전용 변화량 컬럼입니다.
    "delta_spectrum",
    "direction",
    "flagged_wl",
    "ref_dates",
]
SCORE_FRAME_COLUMNS = [*SCORE_COLUMNS, "pm_date"]


class PmComparisonServiceError(Exception):
    """PM SPIDER 서비스 오류를 HTTP 상태와 함께 표현합니다."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        """오류 메시지와 상태 코드를 저장합니다."""

        super().__init__(message)
        self.status_code = status_code
