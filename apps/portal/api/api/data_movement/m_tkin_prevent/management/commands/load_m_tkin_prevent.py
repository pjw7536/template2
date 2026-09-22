"""m_tkin_prevent 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.m_tkin_prevent import services


class Command(DataMovementLoadCommand):
    """Airflow에서 호출할 m_tkin_prevent 파일 적재 command입니다."""

    help = "Load m_tkin_prevent deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_m_tkin_prevent_files"
    table_name = "m_tkin_prevent"
