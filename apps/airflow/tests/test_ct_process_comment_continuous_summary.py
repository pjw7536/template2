"""ct_process_comment 연속 요약 DAG API 계약 테스트입니다."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class _DummyDAG:
    """DAG import에 필요한 context manager만 제공합니다."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "_DummyDAG":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _load_dag_module():
    """Airflow 설치 없이 연속 요약 DAG를 로드합니다."""

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    operators_module = types.ModuleType("airflow.operators")
    python_operator_module = types.ModuleType("airflow.operators.python")
    python_operator_module.PythonOperator = MagicMock
    utils_module = types.ModuleType("airflow.utils")
    dates_module = types.ModuleType("airflow.utils.dates")
    dates_module.days_ago = lambda _days: None
    failure_alerts_module = types.ModuleType("failure_alerts")
    failure_alerts_module.notify_airflow_task_failure = MagicMock()

    module_path = (
        Path(__file__).resolve().parents[1]
        / "dags"
        / "ct_process_comment_openwebui_continuous_summary.py"
    )
    spec = importlib.util.spec_from_file_location("ct_process_comment_continuous_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("연속 요약 DAG module을 로드할 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "airflow": airflow_module,
            "airflow.operators": operators_module,
            "airflow.operators.python": python_operator_module,
            "airflow.utils": utils_module,
            "airflow.utils.dates": dates_module,
            "failure_alerts": failure_alerts_module,
        },
    ):
        spec.loader.exec_module(module)
    return module


DAG_MODULE = _load_dag_module()


class CtProcessCommentContinuousSummaryDagTests(unittest.TestCase):
    """연속 DAG가 DB/OpenWebUI 대신 canonical API만 소비하는지 검증합니다."""

    def test_request_summary_batch_uses_internal_api_contract(self) -> None:
        """batch limit과 bearer token을 Django summary endpoint에 전달합니다."""

        response = MagicMock()
        response.json.return_value = {"processedCount": 2, "failureCount": 0}
        with (
            patch.object(DAG_MODULE, "AIRFLOW_TRIGGER_TOKEN", "test-token"),
            patch.object(DAG_MODULE, "AIRFLOW_API_BASE_URL", "http://api:8000"),
            patch.object(DAG_MODULE.requests, "post", return_value=response) as post,
        ):
            result = DAG_MODULE._request_summary_batch(limit=25)

        self.assertEqual(result["processedCount"], 2)
        self.assertEqual(post.call_args.kwargs["json"], {"limit": 25})
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )


if __name__ == "__main__":
    unittest.main()
