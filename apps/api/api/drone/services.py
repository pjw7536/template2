"""Drone feature service layer.

Implementation is split by functional area for readability:
 - Early inform CRUD: `services_early_inform.py`
 - Drone SOP POP3 ingest: `services_sop_pop3.py`
 - Drone SOP Jira integration: `services_sop_jira.py`
 - Shared helpers: `services_utils.py`

This module acts as a stable import facade (e.g. `from api.drone import services`).
"""

from __future__ import annotations

from .services_early_inform import (
    DroneEarlyInformDuplicateError,
    DroneEarlyInformNotFoundError,
    DroneEarlyInformUpdateResult,
    create_early_inform_entry,
    delete_early_inform_entry,
    update_early_inform_entry,
)
from .services_sop_jira import (
    DroneJiraConfig,
    DroneSopInstantInformResult,
    DroneSopJiraCreateResult,
    _jira_session,
    _update_drone_sop_jira_status,
    run_drone_sop_jira_create_from_env,
    run_drone_sop_jira_instant_inform,
)
from .services_sop_pop3 import (
    DroneSopPop3Config,
    DroneSopPop3IngestResult,
    _build_drone_sop_row,
    _upsert_drone_sop_rows,
    run_drone_sop_pop3_ingest_from_env,
)
from .services_utils import (
    _lock_key,
    _parse_bool,
    _parse_int,
    _release_advisory_lock,
    _try_advisory_lock,
)

__all__ = [
    "DroneEarlyInformDuplicateError",
    "DroneEarlyInformNotFoundError",
    "DroneEarlyInformUpdateResult",
    "DroneJiraConfig",
    "DroneSopInstantInformResult",
    "DroneSopJiraCreateResult",
    "DroneSopPop3Config",
    "DroneSopPop3IngestResult",
    "_build_drone_sop_row",
    "_jira_session",
    "_lock_key",
    "_parse_bool",
    "_parse_int",
    "_release_advisory_lock",
    "_try_advisory_lock",
    "_update_drone_sop_jira_status",
    "_upsert_drone_sop_rows",
    "create_early_inform_entry",
    "delete_early_inform_entry",
    "run_drone_sop_jira_create_from_env",
    "run_drone_sop_jira_instant_inform",
    "run_drone_sop_pop3_ingest_from_env",
    "update_early_inform_entry",
]
