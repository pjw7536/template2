"""스케줄러 또는 두 워커에 CPU와 메모리 부하를 거는 수동 DAG입니다.

**Trigger DAG**의 `target`에서 대상을 선택합니다. `scheduler`는 스케줄러의 cgroup 한도 안에서
기본 120초 실행합니다. `workers`는 두 워커에서 기본 1시간 동안 코어마다 프로세스를 띄워
결과를 검증하는 계산(해시 대조·압축 왕복·정렬·행렬 곱·소수 계산·메모리 다시 쓰기)을 쉬지 않고 수행하고,
테스트 Pod가 밀려나지 않는 한도까지 메모리를 채웁니다. CPU를 양보하지 않는 일반 우선순위로 실행합니다.
워커 테스트에는 전용 Kubernetes namespace와 스케줄러 접근 권한이 필요합니다.
실행 로그에서 평균 CPU 코어 수, 사용 메모리, 계산 건수와 검증 실패 수를 확인할 수 있습니다.
"""

from __future__ import annotations

import hashlib
import logging
import math
import mmap
import multiprocessing
import os
import random
import sys
import time
import zlib
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
MIN_WORKER_MEMORY_MARGIN_BYTES = 512 * MIB
WORKER_CONTROL_INTERVAL_SECONDS = 0.2
WORKER_PROGRESS_INTERVAL_SECONDS = 60
PRIME_LIMIT = 2_000_000
PRIME_COUNT = 148_933
MATRIX_SIZE = 96
SORT_SIZE = 200_000
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


def _burn_cpu(stop: Event) -> None:
    while not stop.is_set():
        # CPython은 OpenSSL의 PBKDF2 계산 중 GIL을 해제합니다.
        hashlib.pbkdf2_hmac("sha256", b"airflow-load-test", b"synthetic", 50_000)


def _run_resource_load(duration: int) -> None:
    """스케줄러 컨테이너에 정해진 시간 동안 부하를 걸고 종료 시 스레드와 메모리를 해제합니다."""

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
            cpu_jobs = [executor.submit(_burn_cpu, stop) for _ in range(cpu_capacity)]
            while (remaining := deadline - time.monotonic()) > 0:
                for job in cpu_jobs:
                    if job.done():
                        job.result()
                available = min(target - int(current.read_text()) for current, target in memory_targets.items())
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


def _worker_memory_headroom(limit_bytes: int) -> int:
    """테스트 Pod가 밀려나지 않고 더 쓸 수 있는 노드 메모리를 계산합니다.

    노드가 시스템용으로 남겨 둔 몫(전체 메모리 - Pod 한도)까지 쓰면 Pod 전체의 한도에 걸려 테스트가 먼저 종료됩니다.
    그 몫과 순간 변동용 여유만 남기고 나머지는 모두 사용 대상으로 봅니다.
    """

    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        field, _, value = line.partition(":")
        if field in {"MemAvailable", "MemTotal"}:
            memory[field] = int(value.split()[0]) * 1024
    margin = max(MIN_WORKER_MEMORY_MARGIN_BYTES, memory["MemTotal"] // 100)
    return memory["MemAvailable"] - max(0, memory["MemTotal"] - limit_bytes) - margin


def _cpu_usage_seconds() -> float | None:
    """현재 cgroup이 지금까지 쓴 CPU 시간입니다. 읽을 수 없으면 None입니다."""

    try:
        for line in (_cgroup_paths()[0] / "cpu.stat").read_text().splitlines():
            name, _, value = line.partition(" ")
            if name == "usage_usec":
                return int(value) / 1_000_000
    except (OSError, RuntimeError, ValueError):
        pass
    return None


def _new_block(rng: random.Random) -> tuple[mmap.mmap, bytes]:
    """난수로 채운 메모리 블록과 그 SHA-256을 만듭니다. 모든 페이지에 실제로 씁니다."""

    data = rng.randbytes(MEMORY_BLOCK_BYTES)
    block = mmap.mmap(-1, MEMORY_BLOCK_BYTES, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
    block[:] = data
    return block, hashlib.sha256(data).digest()


def _task_hash(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """보유한 메모리 블록 하나를 다시 해시해 기록한 값과 대조합니다."""

    if not blocks:
        return hashlib.sha256(scratch).digest() == hashlib.sha256(bytes(scratch)).digest()
    block, digest = blocks[rng.randrange(len(blocks))]
    return hashlib.sha256(block).digest() == digest


def _task_compress(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """1MiB 구간을 압축했다가 풀어 원본과 같은지 확인합니다."""

    if blocks:
        block, _ = blocks[rng.randrange(len(blocks))]
        offset = rng.randrange(0, MEMORY_BLOCK_BYTES - MIB + 1, mmap.PAGESIZE)
        source = block[offset:offset + MIB]
    else:
        source = scratch
    return zlib.decompress(zlib.compress(source, 6)) == source


def _task_sort(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """난수 정수를 정렬하고 순서와 합이 유지되는지 확인합니다."""

    values = [rng.getrandbits(48) for _ in range(SORT_SIZE)]
    total = sum(values)
    values.sort()
    return sum(values) == total and all(left <= right for left, right in zip(values, values[1:]))


def _task_matrix(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """정수 행렬 곱을 계산하고 (A·B)·v = A·(B·v)로 결과를 검증합니다."""

    size = MATRIX_SIZE
    a = [[rng.randrange(1_000) for _ in range(size)] for _ in range(size)]
    b = [[rng.randrange(1_000) for _ in range(size)] for _ in range(size)]
    vector = [rng.randrange(1_000) for _ in range(size)]
    columns = list(zip(*b))
    product = [[sum(x * y for x, y in zip(row, column)) for column in columns] for row in a]
    b_vector = [sum(x * y for x, y in zip(row, vector)) for row in b]
    left = [sum(x * y for x, y in zip(row, vector)) for row in product]
    return left == [sum(x * y for x, y in zip(row, b_vector)) for row in a]


def _task_primes(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """에라토스테네스의 체로 소수 개수를 구해 알려진 값과 대조합니다."""

    sieve = bytearray([1]) * (PRIME_LIMIT + 1)
    sieve[0:2] = bytes(2)
    for number in range(2, math.isqrt(PRIME_LIMIT) + 1):
        if sieve[number]:
            sieve[number * number::number] = bytes(len(range(number * number, PRIME_LIMIT + 1, number)))
    return sum(sieve) == PRIME_COUNT


def _task_rewrite(rng: random.Random, blocks: list, scratch: bytes) -> bool:
    """메모리 블록 하나를 새 난수로 다시 쓰고 읽어서 확인합니다."""

    if not blocks:
        return True
    index = rng.randrange(len(blocks))
    block, _ = blocks[index]
    data = rng.randbytes(MEMORY_BLOCK_BYTES)
    block[:] = data
    digest = hashlib.sha256(data).digest()
    blocks[index] = (block, digest)
    return hashlib.sha256(block).digest() == digest


COMPUTE_TASKS = (
    ("해시", _task_hash),
    ("압축", _task_compress),
    ("정렬", _task_sort),
    ("행렬", _task_matrix),
    ("소수", _task_primes),
    ("쓰기", _task_rewrite),
)


def _compute_worker(index: int, stop, deadline: float, quotas, held, counters, failures) -> None:
    """코어 하나를 맡아 계산 작업을 쉬지 않고 돌리고, 배정받은 수만큼 메모리 블록을 보유합니다."""

    rng = random.Random((os.getpid() << 32) ^ time.monotonic_ns())
    scratch = rng.randbytes(MIB)
    blocks: list[tuple[mmap.mmap, bytes]] = []
    step = 0
    try:
        while not stop.is_set() and time.monotonic() < deadline:
            quota = quotas[index]
            if len(blocks) < quota:
                try:
                    blocks.append(_new_block(rng))
                except (MemoryError, OSError):
                    # 지금은 더 받을 수 없습니다. 다음 주기에 다시 시도합니다.
                    pass
            elif len(blocks) > quota:
                blocks.pop()[0].close()
            held[index] = len(blocks)
            position = step % len(COMPUTE_TASKS)
            if not COMPUTE_TASKS[position][1](rng, blocks, scratch):
                failures[index] += 1
            counters[index * len(COMPUTE_TASKS) + position] += 1
            step += 1
    finally:
        for block, _ in blocks:
            block.close()
        held[index] = 0


def _plan_quota(total_quota: int, held_total: int, available: int) -> int:
    """더 쓸 수 있는 메모리와 아직 채우지 않은 배정량으로 전체 블록 배정량을 다시 정합니다."""

    pending = max(0, total_quota - held_total) * MEMORY_BLOCK_BYTES
    return max(0, total_quota + math.floor((available - pending) / MEMORY_BLOCK_BYTES))


def _distribute(total: int, parts: int) -> list[int]:
    """전체 블록 배정량을 프로세스에 고르게 나눕니다."""

    base, extra = divmod(total, parts)
    return [base + (index < extra) for index in range(parts)]


def _run_worker_load(duration: int) -> None:
    """워커 노드에서 정해진 시간 동안 모든 코어와 가능한 메모리를 실제 계산으로 계속 사용합니다."""

    cpu_capacity, memory_targets = _resource_targets()
    limit_bytes = min(memory_targets.values())
    LOGGER.info("최대 부하 시작 · %d초 · 계산 프로세스 %d개 · 일반 우선순위", duration, cpu_capacity)
    for current, target in memory_targets.items():
        LOGGER.info("cgroup %s · 시작 사용량 %d MiB · 목표 %d MiB", current.parent, int(current.read_text()) // MIB, target // MIB)

    # Pod는 `python -c`로 실행되므로 부모 상태를 그대로 물려받는 fork만 쓸 수 있습니다.
    context = multiprocessing.get_context("fork")
    stop = context.Event()
    quotas = context.Array("q", cpu_capacity, lock=False)
    held = context.Array("q", cpu_capacity, lock=False)
    counters = context.Array("q", cpu_capacity * len(COMPUTE_TASKS), lock=False)
    failures = context.Array("q", cpu_capacity, lock=False)
    started_at = time.monotonic()
    deadline = started_at + duration
    started_cpu = _cpu_usage_seconds()

    def spawn(index: int):
        process = context.Process(target=_compute_worker, args=(index, stop, deadline, quotas, held, counters, failures), daemon=True)
        process.start()
        return process

    processes = [spawn(index) for index in range(cpu_capacity)]
    total_quota = restarts = peak_blocks = 0
    next_progress = started_at + min(WORKER_PROGRESS_INTERVAL_SECONDS, max(1, duration // 2))

    def progress(label: str) -> None:
        elapsed = time.monotonic() - started_at
        used_cpu = _cpu_usage_seconds()
        cores = "확인 불가" if started_cpu is None or used_cpu is None else f"{(used_cpu - started_cpu) / elapsed:.1f}코어"
        per_task = [sum(counters[index * len(COMPUTE_TASKS) + position] for index in range(cpu_capacity))
                    for position in range(len(COMPUTE_TASKS))]
        detail = "·".join(f"{name} {count}" for (name, _), count in zip(COMPUTE_TASKS, per_task))
        LOGGER.info(
            "%s · 경과 %d초 · 평균 CPU %s · 메모리 %d MiB(최대 %d MiB) · 계산 %d건(%s) · 검증 실패 %d건 · 프로세스 재시작 %d회",
            label, elapsed, cores, sum(held) * MEMORY_BLOCK_BYTES // MIB, peak_blocks * MEMORY_BLOCK_BYTES // MIB,
            sum(per_task), detail, sum(failures), restarts,
        )

    try:
        while (remaining := deadline - time.monotonic()) > 0:
            for index, process in enumerate(processes):
                if not process.is_alive():
                    # 메모리 한도에 걸려 종료된 프로세스는 다시 띄워 부하를 이어 갑니다.
                    held[index] = 0
                    processes[index] = spawn(index)
                    restarts += 1
            available = min(target - int(current.read_text()) for current, target in memory_targets.items())
            available = min(available, _worker_memory_headroom(limit_bytes))
            held_total = sum(held)
            total_quota = _plan_quota(total_quota, held_total, available)
            for index, quota in enumerate(_distribute(total_quota, cpu_capacity)):
                quotas[index] = quota
            peak_blocks = max(peak_blocks, held_total)
            if time.monotonic() >= next_progress:
                progress("진행")
                next_progress += WORKER_PROGRESS_INTERVAL_SECONDS
            time.sleep(min(WORKER_CONTROL_INTERVAL_SECONDS, remaining))
    finally:
        stop.set()
        for process in processes:
            process.join(timeout=30)
            if process.is_alive():
                process.terminate()

    progress("최대 부하 종료")
    if sum(failures):
        raise RuntimeError(f"계산 검증 실패 {sum(failures)}건: 메모리 또는 CPU 오류 가능성이 있습니다.")


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
    # 테스트 Pod의 표준 출력으로 진행 상황을 남겨 Airflow 태스크 로그에서 볼 수 있게 합니다.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
    _run_worker_load(int(sys.argv[1]))
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
                description="비워 두면 scheduler는 120초, workers는 3,600초로 실행합니다. workers는 그 시간 동안 두 노드의 모든 코어와 가능한 메모리를 계속 사용합니다.",
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
