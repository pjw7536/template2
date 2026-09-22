"""eqp_status_chg 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.eqp_status_chg import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 eqp_status_chg 파일 적재 command입니다."""

    help = "Load eqp_status_chg deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_eqp_status_chg_files"
    table_name = "eqp_status_chg"
