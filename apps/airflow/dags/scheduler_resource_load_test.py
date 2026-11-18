"""스케줄러 컨테이너에 CPU와 메모리 부하를 동시에 거는 수동 DAG입니다.

Airflow에서 **Trigger DAG**를 선택하고 필요한 경우 부하 시간만 조정합니다.
LocalExecutor의 작업은 스케줄러와 자원을 공유하므로 테스트 중 다른 DAG가 느려질 수 있습니다.
CPU는 할당된 코어와 cgroup 한도를 기준으로 사용합니다.
Linux cgroup v2의 유한한 메모리 한도에서 기존 사용량과 여유분을 뺀 공간을 채웁니다.
작업 로그에서 실제 CPU 스레드 수와 추가로 확보한 최대 메모리를 확인할 수 있습니다.
"""

from __future__ import annotations

import hashlib
import logging
import math
import mmap
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG, Param

MIB = 1024 * 1024
MEMORY_BLOCK_BYTES = 16 * MIB
MIN_MEMORY_HEADROOM_BYTES = 64 * MIB
MEMORY_POLL_INTERVAL_SECONDS = 0.1
MAX_DURATION_SECONDS = 900
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


def run_resource_load(params: dict[str, int]) -> None:
    """정해진 시간 동안 부하를 걸고 종료 시 스레드와 메모리를 해제합니다."""

    duration = int(params["duration_seconds"])
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
    deadline = time.monotonic() + duration
    with ThreadPoolExecutor(max_workers=cpu_capacity) as executor:
        try:
            cpu_jobs = [executor.submit(_burn_cpu, stop) for _ in range(cpu_capacity)]
            while (remaining := deadline - time.monotonic()) > 0:
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

    LOGGER.info("부하 종료 · 최대 추가 메모리 %d MiB", peak_blocks * MEMORY_BLOCK_BYTES // MIB)


with DAG(
    dag_id="scheduler_resource_load_test",
    description="LocalExecutor 스케줄러 CPU·메모리 부하 테스트",
    doc_md=__doc__,
    schedule=None,
    start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    tags=["load-test"],
    default_args={"owner": "airflow", "retries": 0},
    params={
        "duration_seconds": Param(120, type="integer", minimum=1, maximum=MAX_DURATION_SECONDS),
    },
) as dag:
    PythonOperator(
        task_id="load_cpu_and_memory",
        python_callable=run_resource_load,
        execution_timeout=timedelta(seconds=MAX_DURATION_SECONDS + 30),
        do_xcom_push=False,
    )
