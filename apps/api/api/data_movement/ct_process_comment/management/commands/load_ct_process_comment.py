"""ct_process_comment 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.ct_process_comment import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 ct_process_comment 파일 적재 command입니다."""

    help = "Load CT_PROCESS_COMMENT deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_ct_process_comment_files"
    table_name = "ct_process_comment"
