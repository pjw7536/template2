"""station_master 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.station_master import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 station_master 파일 적재 command입니다."""

    help = "Load station_master deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_station_master_files"
    table_name = "station_master"
    outcome_fields = (
        ("rows", "row_count", None),
        ("scope", "replace_scope", None),
    )
