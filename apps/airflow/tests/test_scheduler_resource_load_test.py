"""부하 테스트 DAG의 워커 모드가 검증 가능한 계산을 계속 수행하고 메모리 배정을 한도 안에서 조정하는지 확인합니다."""

from __future__ import annotations

import importlib.util
import logging
import random
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _stub_modules() -> dict[str, types.ModuleType]:
    """Airflow와 Kubernetes client 없이 DAG 파일을 읽을 수 있게 최소한의 대역을 만듭니다."""

    class Operator:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.task_id = kwargs.get("task_id")

        def __rshift__(self, other):
            return other

        def execute(self, context):
            return None

    class Dag:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    modules = {name: types.ModuleType(name) for name in (
        "airflow", "airflow.providers", "airflow.providers.cncf", "airflow.providers.cncf.kubernetes",
        "airflow.providers.cncf.kubernetes.operators", "airflow.providers.cncf.kubernetes.operators.pod",
        "airflow.providers.standard", "airflow.providers.standard.operators", "airflow.providers.standard.operators.python",
        "airflow.sdk", "kubernetes", "kubernetes.client")}
    modules["airflow.providers.cncf.kubernetes.operators.pod"].KubernetesPodOperator = Operator
    modules["airflow.providers.standard.operators.python"].BranchPythonOperator = Operator
    modules["airflow.providers.standard.operators.python"].PythonOperator = Operator
    modules["airflow.sdk"].DAG = Dag
    modules["airflow.sdk"].Param = lambda *args, **kwargs: (args, kwargs)
    modules["kubernetes.client"].AppsV1Api = object
    modules["kubernetes.client"].V1ResourceRequirements = dict
    return modules


with patch.dict(sys.modules, _stub_modules()):
    SPEC = importlib.util.spec_from_file_location(
        "scheduler_resource_load_test_under_test",
        Path(__file__).resolve().parents[1] / "dags/scheduler_resource_load_test.py",
    )
    load = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(load)

BLOCK = load.MEMORY_BLOCK_BYTES


class ComputeTaskTests(unittest.TestCase):
    """각 계산 작업이 정상 결과를 통과시키고 틀린 결과를 잡아내는지 확인합니다."""

    def setUp(self):
        self.rng = random.Random(7)
        self.scratch = self.rng.randbytes(load.MIB)
        self.blocks = [load._new_block(self.rng) for _ in range(2)]
        self.addCleanup(lambda: [block.close() for block, _ in self.blocks])

    def test_every_task_passes_with_and_without_memory_blocks(self):
        for name, task in load.COMPUTE_TASKS:
            with self.subTest(task=name):
                self.assertTrue(task(self.rng, self.blocks, self.scratch))
                self.assertTrue(task(self.rng, [], self.scratch))

    def test_hash_task_detects_a_changed_memory_block(self):
        for block, _ in self.blocks:
            block[0:1] = bytes([block[0] ^ 0xFF])
        self.assertFalse(load._task_hash(self.rng, self.blocks, self.scratch))

    def test_rewrite_task_replaces_the_block_and_its_recorded_digest(self):
        before = [digest for _, digest in self.blocks]
        self.assertTrue(load._task_rewrite(self.rng, self.blocks, self.scratch))
        self.assertNotEqual([digest for _, digest in self.blocks], before)
        # 다시 쓴 뒤에도 기록한 값과 메모리 내용이 맞아야 합니다.
        self.assertTrue(all(load.hashlib.sha256(block).digest() == digest for block, digest in self.blocks))

    def test_prime_count_constant_matches_an_independent_count(self):
        limit = load.PRIME_LIMIT
        flags = [True] * (limit + 1)
        flags[0] = flags[1] = False
        number = 2
        while number * number <= limit:
            if flags[number]:
                for multiple in range(number * number, limit + 1, number):
                    flags[multiple] = False
            number += 1
        self.assertEqual(flags.count(True), load.PRIME_COUNT)

    def test_wrong_expected_value_is_reported_as_a_failure(self):
        with patch.object(load, "PRIME_COUNT", load.PRIME_COUNT + 1):
            self.assertFalse(load._task_primes(self.rng, [], self.scratch))


class MemoryPlanTests(unittest.TestCase):
    def test_quota_grows_by_what_is_available_minus_what_is_not_filled_yet(self):
        # 아직 채우지 않은 배정량을 빼지 않으면 사용량이 따라오기 전에 계속 늘려 한도를 넘깁니다.
        self.assertEqual(load._plan_quota(0, 0, 10 * BLOCK), 10)
        self.assertEqual(load._plan_quota(10, 4, 10 * BLOCK), 14)
        self.assertEqual(load._plan_quota(10, 10, BLOCK - 1), 10)

    def test_quota_shrinks_when_other_workloads_need_memory_and_never_goes_negative(self):
        self.assertEqual(load._plan_quota(10, 10, -3 * BLOCK), 7)
        self.assertEqual(load._plan_quota(10, 10, -BLOCK // 2), 9)
        self.assertEqual(load._plan_quota(2, 2, -100 * BLOCK), 0)

    def test_quota_is_spread_evenly_over_processes(self):
        self.assertEqual(load._distribute(10, 4), [3, 3, 2, 2])
        self.assertEqual(load._distribute(0, 3), [0, 0, 0])
        self.assertEqual(sum(load._distribute(1234, 32)), 1234)

    def test_node_headroom_keeps_the_system_share_and_a_small_margin_only(self):
        gib = 1024 * load.MIB
        meminfo = f"MemTotal: {64 * gib // 1024} kB\nMemFree: 1 kB\nMemAvailable: {40 * gib // 1024} kB\n"
        fake_path = lambda name: types.SimpleNamespace(read_text=lambda: meminfo)
        with patch.object(load, "Path", fake_path):
            # Pod 한도가 60GiB면 노드가 시스템용으로 남긴 4GiB와 여유(전체의 1%)만 남기고 모두 씁니다.
            self.assertEqual(load._worker_memory_headroom(60 * gib), 40 * gib - 4 * gib - 64 * gib // 100)
            # 한도가 전체 메모리 이상이어도 여유는 남깁니다.
            self.assertEqual(load._worker_memory_headroom(64 * gib), 40 * gib - 64 * gib // 100)


class WorkerLoadRunTests(unittest.TestCase):
    """작은 메모리 한도와 프로세스 두 개로 실제 실행 흐름을 확인합니다."""

    def run_load(self, duration=2):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        current = Path(directory.name) / "memory.current"
        current.write_text("0")
        # 처음 한 번만 블록 4개를 허용합니다. 이후에는 추가 여유가 없는 노드처럼 동작합니다.
        headroom = iter([4 * BLOCK])
        with patch.object(load, "_resource_targets", return_value=(2, {current: 1024 * BLOCK})), \
                patch.object(load, "_worker_memory_headroom", side_effect=lambda limit: next(headroom, 0)), \
                patch.object(load, "_cpu_usage_seconds", return_value=None), \
                self.assertLogs(load.LOGGER, level=logging.INFO) as logs:
            try:
                load._run_worker_load(duration)
            finally:
                self.output = "\n".join(logs.output)
        return self.output

    def test_runs_real_computation_on_every_process_and_holds_the_allowed_memory(self):
        output = self.run_load()
        self.assertIn("계산 프로세스 2개 · 일반 우선순위", output)
        summary = next(line for line in output.splitlines() if "최대 부하 종료" in line)
        self.assertIn("검증 실패 0건", summary)
        self.assertIn(f"최대 {4 * BLOCK // load.MIB} MiB", summary)
        counts = dict(part.rsplit(" ", 1) for part in summary.split("건(")[1].split(")")[0].split("·"))
        self.assertEqual(set(counts), {name for name, _ in load.COMPUTE_TASKS})
        self.assertTrue(all(int(count) > 0 for count in counts.values()), counts)

    def test_wrong_result_fails_the_run_after_the_full_duration(self):
        tasks = (("해시", lambda rng, blocks, scratch: False), *load.COMPUTE_TASKS[1:])
        with patch.object(load, "COMPUTE_TASKS", tasks), self.assertRaisesRegex(RuntimeError, "계산 검증 실패"):
            self.run_load(duration=1)
        self.assertIn("최대 부하 종료", self.output)


class TargetSelectionTests(unittest.TestCase):
    def test_workers_target_runs_one_task_per_fixed_node(self):
        selected = load._select_target({"target": "workers", "duration_seconds": 60})
        self.assertEqual(selected, [f"load_{node}" for node in load.TEST_NODES])
        self.assertEqual(len(load.TEST_NODES), 2)
        self.assertEqual(load._select_target({"target": "scheduler"}), "load_cpu_and_memory")

    def test_duration_defaults_and_limits_depend_on_the_target(self):
        self.assertEqual(load._load_duration({"target": "workers"}), 3600)
        self.assertEqual(load._load_duration({"target": "scheduler"}), 120)
        for params in ({"target": "workers", "duration_seconds": 5}, {"target": "scheduler", "duration_seconds": 901}):
            with self.assertRaises(ValueError):
                load._load_duration(params)


if __name__ == "__main__":
    unittest.main()
