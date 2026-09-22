"""mes_line_mapping_info 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.mes_line_mapping_info import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 mes_line_mapping_info 파일 적재 command입니다."""

    help = "Load mes_line_mapping_info deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_mes_line_mapping_info_files"
    table_name = "mes_line_mapping_info"
    outcome_fields = (
        ("rows", "row_count", None),
        ("scope", "replace_scope", None),
    )
