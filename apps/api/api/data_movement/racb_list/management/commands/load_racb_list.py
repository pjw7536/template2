"""racb_list 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.racb_list import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 racb_list 파일 적재 command입니다."""

    help = "Load racb_list deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_racb_list_files"
    table_name = "racb_list"
