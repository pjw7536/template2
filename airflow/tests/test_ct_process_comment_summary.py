"""ct_process_comment summary DAG 오류 포맷 테스트입니다."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class _DummyDAG:
    """DAG module import 중 context manager 동작만 대체합니다."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "_DummyDAG":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _load_dag_module():
    """Airflow 설치 없이 오류 포맷 함수가 있는 DAG module을 로드합니다."""

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    operators_module = types.ModuleType("airflow.operators")
    python_operator_module = types.ModuleType("airflow.operators.python")
    python_operator_module.PythonOperator = Mock
    utils_module = types.ModuleType("airflow.utils")
    dates_module = types.ModuleType("airflow.utils.dates")
    dates_module.days_ago = lambda _days: None
    failure_alerts_module = types.ModuleType("failure_alerts")
    failure_alerts_module.notify_airflow_task_failure = Mock()

    module_path = Path(__file__).resolve().parents[1] / "dags" / "ct_process_comment_summary.py"
    spec = importlib.util.spec_from_file_location("ct_process_comment_summary_under_test", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ct_process_comment_summary DAG module을 로드할 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    stub_modules = {
        "airflow": airflow_module,
        "airflow.operators": operators_module,
        "airflow.operators.python": python_operator_module,
        "airflow.utils": utils_module,
        "airflow.utils.dates": dates_module,
        "failure_alerts": failure_alerts_module,
    }
    with patch.dict(sys.modules, stub_modules):
        spec.loader.exec_module(module)
    return module


DAG_MODULE = _load_dag_module()


class CtProcessCommentSummaryDagTests(unittest.TestCase):
    """Airflow 오류가 반복 outcome 때문에 잘리지 않는지 검증합니다."""

    def test_format_error_response_groups_repeated_failures(self) -> None:
        """동일 원인 99건은 대표 오류 한 건과 workorder 샘플로 집계합니다."""

        outcomes = [
            {
                "workorder_id": f"WO-{index:03d}",
                "status": "failed",
                "error_message": (
                    "OpenWebUI 모든 응답 방식에서 최종 content 추출에 실패했습니다. "
                    "diagnostic_version='ctpc-openwebui-v2', stage=event_summary, "
                    f"response_id='chatcmpl-{index:03d}'"
                ),
            }
            for index in range(99)
        ]
        response = Mock()
        response.json.return_value = {
            "table_name": "ct_process_comment",
            "processed_count": 100,
            "success_count": 1,
            "failure_count": 99,
            "outcomes": outcomes,
        }

        detail = json.loads(DAG_MODULE._format_error_response(response))

        self.assertEqual(detail["failed_outcome_count"], 99)
        self.assertEqual(detail["failure_group_count"], 1)
        self.assertEqual(detail["omitted_failure_group_count"], 0)
        self.assertEqual(detail["failure_groups"][0]["failure_count"], 99)
        self.assertEqual(
            detail["failure_groups"][0]["sample_workorder_ids"],
            ["WO-000", "WO-001", "WO-002", "WO-003", "WO-004"],
        )
        self.assertIn(
            "diagnostic_version='ctpc-openwebui-v2'",
            detail["failure_groups"][0]["representative_error"],
        )
        self.assertLess(len(json.dumps(detail, ensure_ascii=False)), 20000)

    def test_format_error_response_reports_omitted_failure_groups(self) -> None:
        """서로 다른 원인이 제한보다 많으면 생략된 그룹 수를 명시합니다."""

        response = Mock()
        response.json.return_value = {
            "failure_count": 3,
            "outcomes": [
                {
                    "workorder_id": f"WO-{index}",
                    "status": "failed",
                    "error_message": f"원인-{index}. stage=event_summary",
                }
                for index in range(3)
            ],
        }

        detail = json.loads(DAG_MODULE._format_error_response(response))

        self.assertEqual(detail["failure_group_count"], 3)
        self.assertEqual(len(detail["failure_groups"]), 2)
        self.assertEqual(detail["omitted_failure_group_count"], 1)


if __name__ == "__main__":
    unittest.main()
