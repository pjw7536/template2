#!/usr/bin/env python3
"""기존 server-up 명령을 Airflow 소유의 통합 기동 도구로 연결한다."""

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    """실행할 때만 Airflow 구현을 읽어 기존 명령과 옵션을 유지한다."""
    spec = importlib.util.spec_from_file_location('deploy_runtime', ROOT / 'deploy/shared/scripts/runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    server = runtime.module('airflow_server', ROOT / 'deploy/airflow/scripts/server.py')
    server.main()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
