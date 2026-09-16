"""m_interlock 파일 적재 management command입니다."""

from __future__ import annotations

from api.data_movement.common.services import DataMovementLoadCommand
from api.data_movement.m_interlock import services


class Command(DataMovementLoadCommand):
    """m_interlock 파일 적재를 수동 또는 scheduler에서 실행합니다."""

    help = "Load m_interlock deflate CSV files into PostgreSQL."
    service_module = services
    loader_name = "load_m_interlock_files"
    table_name = "m_interlock"
