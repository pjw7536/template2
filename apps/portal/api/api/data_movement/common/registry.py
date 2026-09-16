"""Data Movement 적재기 registry입니다."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable


LoadFunction = Callable[..., Any]


@dataclass(frozen=True)
class DataMovementLoaderDefinition:
    """테이블 이름과 적재기 import 경로를 묶습니다."""

    table_name: str
    module_path: str
    callable_name: str
    lifecycle: str = "incoming_processing"

    def resolve(self) -> LoadFunction:
        """등록된 적재기 callable을 지연 import합니다."""

        module = import_module(self.module_path)
        return getattr(module, self.callable_name)


DATA_MOVEMENT_LOADER_REGISTRY = {
    definition.table_name: definition
    for definition in (
        DataMovementLoaderDefinition(
            "m_tkin_prevent",
            "api.data_movement.m_tkin_prevent.services",
            "load_m_tkin_prevent_files",
        ),
        DataMovementLoaderDefinition(
            "ctttm_workorder_list",
            "api.data_movement.ctttm_workorder_list.services",
            "load_ctttm_workorder_list_files",
        ),
        DataMovementLoaderDefinition(
            "ct_process_comment",
            "api.data_movement.ct_process_comment.services",
            "load_ct_process_comment_files",
        ),
        DataMovementLoaderDefinition(
            "eqp_status_chg",
            "api.data_movement.eqp_status_chg.services",
            "load_eqp_status_chg_files",
        ),
        DataMovementLoaderDefinition(
            "m_interlock",
            "api.data_movement.m_interlock.services",
            "load_m_interlock_files",
        ),
        DataMovementLoaderDefinition(
            "mi_tip_update_hist",
            "api.data_movement.mi_tip_update_hist.services",
            "load_mi_tip_update_hist_files",
        ),
        DataMovementLoaderDefinition(
            "racb_list",
            "api.data_movement.racb_list.services",
            "load_racb_list_files",
        ),
        DataMovementLoaderDefinition(
            "mes_line_mapping_info",
            "api.data_movement.mes_line_mapping_info.services",
            "load_mes_line_mapping_info_files",
        ),
        DataMovementLoaderDefinition(
            "station_master",
            "api.data_movement.station_master.services",
            "load_station_master_files",
        ),
    )
}


def get_data_movement_loader(table_name: str) -> LoadFunction | None:
    """테이블 이름에 해당하는 적재기를 반환합니다."""

    definition = DATA_MOVEMENT_LOADER_REGISTRY.get(table_name)
    return definition.resolve() if definition is not None else None


__all__ = [
    "DATA_MOVEMENT_LOADER_REGISTRY",
    "DataMovementLoaderDefinition",
    "get_data_movement_loader",
]
