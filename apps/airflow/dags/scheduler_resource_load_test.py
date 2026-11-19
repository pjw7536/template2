"""스케줄러 또는 두 워커에 CPU와 메모리 부하를 거는 수동 DAG입니다.

**Trigger DAG**의 `target`에서 대상을 선택합니다. `scheduler`는 스케줄러의 cgroup 한도 안에서
기본 120초, `workers`는 두 워커에서 낮은 우선순위로 기본 1시간 실행합니다.
워커 테스트에는 전용 Kubernetes namespace와 스케줄러 접근 권한이 필요합니다.
실행 로그에서 평균 CPU 코어 수와 최대 추가 메모리를 확인할 수 있습니다.
"""

from __future__ import annotations

import hashlib
import logging
import math
import mmap
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import BranchPythonOperator, PythonOperator
from airflow.sdk import DAG, Param
from kubernetes.client import AppsV1Api, V1ResourceRequirements

MIB = 1024 * 1024
MEMORY_BLOCK_BYTES = 16 * MIB
MIN_MEMORY_HEADROOM_BYTES = 64 * MIB
MEMORY_POLL_INTERVAL_SECONDS = 0.1
MIN_NODE_MEMORY_HEADROOM_BYTES = 4 * 1024 * MIB
MAX_SCHEDULER_DURATION_SECONDS = 900
MAX_WORKER_DURATION_SECONDS = 24 * 60 * 60
START_TIMEOUT_SECONDS = 180
TEST_NAMESPACE = "airflow-node-load-test"
TEST_NODES = ("khinfow01", "khplanew01")
SERVICE_ACCOUNT_NAMESPACE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
LOGGER = logging.getLogger(__name__)


def _cgroup_paths() -> tuple[Path, ...]:
    """현재 프로세스의 cgroup과 마운트에서 보이는 상위 cgroup을 반환합니다."""

    for line in Path("/proc/self/cgroup").read_text().splitlines():
        if line.startswith("0::"):
            cgroup_path = Path(line.removeprefix("0::"))
            break
    else:
        raise RuntimeError("현재 프로세스에서 cgroup v2 경로를 확인할 수 없습니다.")

    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        mount_info, filesystem = line.split(" - ", 1)
        if filesystem.split()[0] != "cgroup2":
            continue
        mount_root, mount_point = map(Path, mount_info.split()[3:5])
        if cgroup_path == Path("/"):
            group = mount_point
        elif cgroup_path.is_relative_to(mount_root):
            group = mount_point / cgroup_path.relative_to(mount_root)
        else:
            continue
        if group.is_dir():
            ancestors = tuple(parent for parent in group.parents if parent.is_relative_to(mount_point))
            return (group, *ancestors)

    raise RuntimeError("현재 프로세스의 cgroup v2 마운트를 찾을 수 없습니다.")


def _resource_targets() -> tuple[int, dict[Path, int]]:
    """스케줄러와 공유하는 상위 cgroup 한도까지 부하 목표에 반영합니다."""

    cpu_capacity = len(os.sched_getaffinity(0))
    memory_targets = {}
    for group in _cgroup_paths():
        cpu_max = group / "cpu.max"
        if cpu_max.is_file():
            quota, period = cpu_max.read_text().split()
            if quota != "max":
                cpu_capacity = min(cpu_capacity, math.ceil(int(quota) / int(period)))

        memory_max = group / "memory.max"
        if memory_max.is_file():
            limit = memory_max.read_text().strip()
            if limit != "max":
                limit_bytes = int(limit)
                # 할당 단위와 스케줄러의 순간 사용량 변동을 고려해 여유를 둡니다.
                headroom = max(MIN_MEMORY_HEADROOM_BYTES, limit_bytes // 100)
                memory_targets[group / "memory.current"] = max(0, limit_bytes - headroom)

    if not memory_targets:
        raise RuntimeError("부하 테스트에는 유한한 cgroup 메모리 한도가 필요합니다.")

    return cpu_capacity, memory_targets


def _burn_cpu(stop: Event, *, idle_priority: bool) -> None:
    if idle_priority:
        # CPU 연산만 낮은 우선순위로 실행해 메모리 반환은 지연되지 않게 합니다.
        os.sched_setscheduler(0, os.SCHED_IDLE, os.sched_param(0))
    while not stop.is_set():
        # CPython은 OpenSSL의 PBKDF2 계산 중 GIL을 해제합니다.
        hashlib.pbkdf2_hmac("sha256", b"airflow-load-test", b"synthetic", 50_000)


def _node_memory_headroom() -> int:
    """노드의 회수 가능 메모리를 포함한 여유에서 운영 서비스용 공간을 남깁니다."""

    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        field, _, value = line.partition(":")
        if field in {"MemAvailable", "MemTotal"}:
            memory[field] = int(value.split()[0]) * 1024
    reserve = max(MIN_NODE_MEMORY_HEADROOM_BYTES, memory["MemTotal"] // 10)
    return memory["MemAvailable"] - reserve


def _run_resource_load(duration: int, *, worker_node: bool = False) -> None:
    """정해진 시간 동안 부하를 걸고 종료 시 스레드와 메모리를 해제합니다."""

    cpu_capacity, memory_targets = _resource_targets()
    LOGGER.info("부하 시작 · %d초 · CPU 스레드 %d개", duration, cpu_capacity)
    for current, target in memory_targets.items():
        LOGGER.info(
            "cgroup %s · 시작 사용량 %d MiB · 목표 %d MiB",
            current.parent,
            int(current.read_text()) // MIB,
            target // MIB,
        )

    stop = Event()
    blocks: list[mmap.mmap] = []
    peak_blocks = 0
    page_markers = b"\x01" * (MEMORY_BLOCK_BYTES // mmap.PAGESIZE)
    started_at = time.monotonic()
    started_cpu = time.process_time()
    deadline = started_at + duration
    with ThreadPoolExecutor(max_workers=cpu_capacity) as executor:
        try:
            cpu_jobs = [executor.submit(_burn_cpu, stop, idle_priority=worker_node) for _ in range(cpu_capacity)]
            while (remaining := deadline - time.monotonic()) > 0:
                for job in cpu_jobs:
                    if job.done():
                        job.result()
                available = min(target - int(current.read_text()) for current, target in memory_targets.items())
                if worker_node:
                    available = min(available, _node_memory_headroom())
                if available >= MEMORY_BLOCK_BYTES:
                    block = mmap.mmap(-1, MEMORY_BLOCK_BYTES, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
                    blocks.append(block)
                    # 페이지에 직접 써서 예약한 주소 공간을 실제 메모리에 올립니다.
                    block[::mmap.PAGESIZE] = page_markers
                    peak_blocks = max(peak_blocks, len(blocks))
                elif available < 0 and blocks:
                    # 다른 작업의 사용량이 늘면 이 DAG가 확보한 메모리를 반환합니다.
                    blocks.pop().close()
                else:
                    time.sleep(min(MEMORY_POLL_INTERVAL_SECONDS, remaining))
        finally:
            stop.set()
            for block in blocks:
                block.close()

        for job in cpu_jobs:
            job.result()

    elapsed = time.monotonic() - started_at
    average_cores = (time.process_time() - started_cpu) / elapsed
    LOGGER.info(
        "부하 종료 · 평균 CPU %.2f코어 · 최대 추가 메모리 %d MiB",
        average_cores,
        peak_blocks * MEMORY_BLOCK_BYTES // MIB,
    )


def _load_duration(params: dict[str, int | str | None]) -> int:
    target = params.get("target", "scheduler")
    if target == "workers":
        default, minimum, maximum = 3600, 10, MAX_WORKER_DURATION_SECONDS
    else:
        default, minimum, maximum = 120, 1, MAX_SCHEDULER_DURATION_SECONDS

    configured_duration = params.get("duration_seconds")
    duration = default if configured_duration is None else int(configured_duration)
    if not minimum <= duration <= maximum:
        raise ValueError(f"{target}의 duration_seconds는 {minimum}~{maximum}초여야 합니다.")
    return duration


def _select_target(params: dict[str, int | str | None]) -> str | list[str]:
    # 테스트 Pod를 생성하기 전에 대상별 실행 시간 제약을 검사합니다.
    _load_duration(params)
    if params.get("target") == "workers":
        return [f"load_{node_name}" for node_name in TEST_NODES]
    return "load_cpu_and_memory"


def run_resource_load(params: dict[str, int | str | None]) -> None:
    """스케줄러 컨테이너의 CPU와 메모리를 테스트합니다."""

    _run_resource_load(_load_duration(params))


class WorkerNodeLoadOperator(KubernetesPodOperator):
    """대상 노드의 할당 가능 자원으로 테스트 Pod의 상한을 설정합니다."""

    def __init__(self, *, node_name: str, **kwargs):
        super().__init__(**kwargs)
        self.node_name = node_name

    def execute(self, context):
        duration = _load_duration(context["params"])
        node = self.client.read_node(self.node_name)
        ready = any(condition.type == "Ready" and condition.status == "True" for condition in node.status.conditions)
        if not ready or node.spec.unschedulable:
            raise RuntimeError(f"{self.node_name} 노드에 테스트 Pod를 배치할 수 없습니다.")

        namespace = SERVICE_ACCOUNT_NAMESPACE.read_text().strip()
        deployment = AppsV1Api(self.client.api_client).read_namespaced_deployment("airflow-scheduler", namespace)
        scheduler_pod = deployment.spec.template.spec
        self.image = next(container.image for container in scheduler_pod.containers if container.name == "scheduler")
        self.image_pull_secrets = scheduler_pod.image_pull_secrets or []
        self.node_selector = {"kubernetes.io/hostname": node.metadata.labels["kubernetes.io/hostname"]}
        self.container_resources = V1ResourceRequirements(
            requests={"cpu": "10m", "memory": "64Mi"},
            limits={resource: node.status.allocatable[resource] for resource in ("cpu", "memory")},
        )
        # 현재 DAG 파일을 전달해 양쪽 워커에서 같은 부하 코드를 실행합니다.
        self.arguments = [Path(__file__).read_text(), str(duration)]
        self.active_deadline_seconds = duration + START_TIMEOUT_SECONDS
        return super().execute(context)


if __name__ == "__main__":
    _run_resource_load(int(sys.argv[1]), worker_node=True)
else:
    with DAG(
        dag_id="scheduler_resource_load_test",
        dag_display_name="CPU·메모리 부하 테스트",
        description="Airflow 스케줄러 또는 Kubernetes 워커의 CPU·메모리 부하 테스트",
        doc_md=__doc__,
        schedule=None,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        catchup=False,
        max_active_runs=1,
        max_active_tasks=len(TEST_NODES),
        tags=["load-test"],
        default_args={"owner": "airflow", "retries": 0},
        params={
            "target": Param("scheduler", type="string", enum=["scheduler", "workers"], title="부하 대상"),
            "duration_seconds": Param(
                None,
                type=["null", "integer"],
                minimum=1,
                maximum=MAX_WORKER_DURATION_SECONDS,
                description="비워 두면 scheduler는 120초, workers는 3,600초로 실행합니다.",
            ),
        },
    ) as dag:
        select_target = BranchPythonOperator(task_id="select_target", python_callable=_select_target)
        select_target >> PythonOperator(
            task_id="load_cpu_and_memory",
            python_callable=run_resource_load,
            execution_timeout=timedelta(seconds=MAX_SCHEDULER_DURATION_SECONDS + 30),
            do_xcom_push=False,
        )

        for node_name in TEST_NODES:
            select_target >> WorkerNodeLoadOperator(
                task_id=f"load_{node_name}",
                node_name=node_name,
                name=f"load-{node_name}",
                random_name_suffix=False,
                kubernetes_conn_id=None,
                in_cluster=True,
                namespace=TEST_NAMESPACE,
                priority_class_name=TEST_NAMESPACE,
                labels={"app.kubernetes.io/name": TEST_NAMESPACE},
                cmds=["python", "-u", "-c"],
                image_pull_policy="IfNotPresent",
                automount_service_account_token=False,
                security_context={"runAsNonRoot": True, "runAsUser": 50000, "seccompProfile": {"type": "RuntimeDefault"}},
                container_security_context={"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}},
                startup_timeout_seconds=START_TIMEOUT_SECONDS,
                schedule_timeout_seconds=START_TIMEOUT_SECONDS,
                execution_timeout=timedelta(seconds=MAX_WORKER_DURATION_SECONDS + 2 * START_TIMEOUT_SECONDS + 60),
                on_finish_action="delete_pod",
                on_kill_action="delete_pod",
                get_logs=True,
                do_xcom_push=False,
            )
