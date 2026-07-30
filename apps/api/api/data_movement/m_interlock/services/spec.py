"""m_interlock 파일 적재 spec입니다."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

TABLE_NAME = "m_interlock"
TEMP_TABLE_NAME = "tmp_m_interlock_upsert"
UPSERT_KEY = "interlock_no"
FILE_PATTERN = "m_interlock_*_????????_????.csv.deflate"
SOURCE_FILE_PATTERN = (
    r"^m_interlock_(?P<line_id>.+)_(?P<file_timestamp>\d{8}_\d{4})\.csv\.deflate$"
)
FILE_SEPARATOR = "`"

DEFAULT_TABLE_DIR = Path(settings.DATA_MOVEMENT_M_INTERLOCK_DIR)

COLUMNS = [
    "line_id",
    "interlock_no",
    "item_value",
    "interlock_type",
    "interlock_comment",
    "ppid",
    "usl",
    "spec_target",
    "lsl",
    "ucl",
    "cl",
    "lcl",
    "batch_id",
    "metro_item",
    "interlock_desc",
    "area_name",
    "process_id",
    "interlock_kind",
    "lot_id",
    "prod_step_seq",
    "prod_progs_time",
    "prod_eqp_type",
    "prod_bay_name",
    "prod_chamber_id",
    "metro_step_seq",
    "metro_progs_time",
    "intlk_occur_week",
    "intlk_occur_year_m",
    "metro_eqp_id",
    "prod_eqp_id",
    "last_update_date",
    "wafer_id",
    "eqp_process_phase",
    "eqp_detail_comment",
    "engr_comment",
]

DATETIME_COLUMNS = ["last_update_date"]
FLOAT_COLUMNS: list[str] = []
