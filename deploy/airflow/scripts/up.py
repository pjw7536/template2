#!/usr/bin/env python3
"""Airflow만 배포하고 필요한 공용 Traefik 연결을 준비한다."""

import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('server_up', ROOT / 'deploy/shared/scripts/server-up.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def main():
    """앱별 env와 context를 받아 DB를 유지하며 배포한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--env', type=Path, default=ROOT / 'deploy/airflow/env/k8s.env')
    parser.add_argument('--tls-source')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    airflow = server.module('airflow_deploy', ROOT / 'deploy/airflow/scripts/manage.py')
    airflow.require(args.context.strip(), '--context를 명시하세요.')
    settings = airflow.read_env(args.env)
    airflow.validate(settings)
    if settings['INGRESS_ENABLED'] == 'true':
        routing = server.module('routing', ROOT / 'deploy/shared/ingress/routing.py')
        server.start(airflow, routing, args.context, args.env, args.tls_source,
                     check_only=args.check_only, deploy_keycloak=False)
    else:
        chart = airflow.chart_path()
        if args.check_only:
            with tempfile.TemporaryDirectory(prefix='airflow-check-') as temporary:
                airflow.render(settings, temporary, chart, pause_new_dags=True)
            airflow.check_cluster_inputs(settings, args.context)
            print('Airflow 설정·차트·클러스터 버전·노드·기존 비밀값 검사 통과. 디스크·이미지·접속 확인은 별도입니다.')
        else:
            airflow.deploy(settings, args.context, chart, pause_new_dags=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(f'오류: {error}', file=sys.stderr)
        sys.exit(1)
