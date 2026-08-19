"""mi_tip_update_hist 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.mi_tip_update_hist import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 mi_tip_update_hist 파일 적재 command입니다."""

    help = "Load mi_tip_update_hist deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_mi_tip_update_hist_files"
    table_name = "mi_tip_update_hist"
