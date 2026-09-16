"""ctttm_workorder_list 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.ctttm_workorder_list import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 ctttm_workorder_list 파일 적재 command입니다."""

    help = "Load CTTTM workorder deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_ctttm_workorder_list_files"
    table_name = "ctttm_workorder_list"
    outcome_fields = (
        ("source", "source_type", "-"),
        ("rows", "row_count", None),
    )
