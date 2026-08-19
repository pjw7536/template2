"""Account 외부 소속 sync DAG의 camelCase 계약 테스트입니다."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class _DummyDAG:
    """DAG module import에 필요한 context manager만 제공합니다."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "_DummyDAG":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _load_dag_module():
    """Airflow 설치 없이 Account sync DAG module을 로드합니다."""

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    python_operator_module = types.ModuleType("airflow.operators.python")
    python_operator_module.PythonOperator = Mock
    dates_module = types.ModuleType("airflow.utils.dates")
    dates_module.days_ago = lambda _days: None
    failure_alerts_module = types.ModuleType("failure_alerts")
    failure_alerts_module.notify_airflow_task_failure = Mock()
    stubs = {
        "airflow": airflow_module,
        "airflow.operators": types.ModuleType("airflow.operators"),
        "airflow.operators.python": python_operator_module,
        "airflow.utils": types.ModuleType("airflow.utils"),
        "airflow.utils.dates": dates_module,
        "failure_alerts": failure_alerts_module,
    }
    module_path = Path(__file__).resolve().parents[1] / "dags" / "account_external_affiliations_sync.py"
    spec = importlib.util.spec_from_file_location("account_external_sync_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Account sync DAG module을 로드할 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class AccountExternalAffiliationsSyncDagTests(unittest.TestCase):
    """사내 원천 column이 canonical API field로 변환되는지 검증합니다."""

    def test_record_columns_are_camel_case(self) -> None:
        """Airflow가 snake_case HTTP key를 다시 보내지 않습니다."""

        module = _load_dag_module()

        self.assertEqual(
            module.EXTERNAL_AFFILIATION_RECORD_COLUMNS,
            ["knoxId", "username", "department", "userSdwtProd", "sourceUpdatedAt"],
        )
        self.assertEqual(module.EXTERNAL_AFFILIATION_COLUMN_RENAMES["sso_id"], "knoxId")
        self.assertEqual(module.EXTERNAL_AFFILIATION_COLUMN_RENAMES["tdvt_nm"], "userSdwtProd")


if __name__ == "__main__":
    unittest.main()
