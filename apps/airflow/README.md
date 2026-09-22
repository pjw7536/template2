# Airflow

Portal API를 호출하는 DAG와 Airflow 이미지 빌드 소스를 관리합니다.

## 파일 위치

| 작업 | 경로 |
| --- | --- |
| 소스·테스트 | `dags/`, `plugins/`, `tests/` |
| 이미지 빌드 | `image/Dockerfile.dependencies`, `image/Dockerfile`, `image/bootstrap-user.py` |
| 서버 배포·빌드 입력 | [deploy/airflow](../../deploy/airflow/README.md)의 Helm·Kubernetes·env |
| 개발 설정·실행 | [local/airflow](../../local/README.md), `local/airflow/helm/values.yaml` |
| 개발 로그 | `data/k8s-local/airflow/logs` |

## 개발·검증

저장소 루트에서 `make dev`로 전체 로컬 Kubernetes를 실행합니다.
DAG·이미지를 변경하면 `make k8s-rebuild APP=airflow`로 반영합니다.
계정과 DB 연결은 공통 로컬 실행 도구가 생성하며 기존 데이터를 보존합니다.

검사 명령은 `python3 -m unittest discover -s apps/airflow/tests -v`,
`node --test apps/tooling/tests/airflow-deployment.test.cjs apps/tooling/tests/app-layout.test.cjs`입니다.

## 빌드·배포

`python3 deploy/airflow/scripts/manage.py build-image --build-env deploy/airflow/env/build.env`를 사용합니다.
의존성 이미지에는 Dockerfile만 전달하고, 최종 이미지 context는 `apps/airflow`입니다.
최종 이미지에는 DAG·플러그인·관리자 초기화 코드가 포함됩니다. 실제 설정·로그는 제외합니다.

기본 서버 checkout은 소스를 제외합니다. 빌드가 필요한 경우
`bash deploy/shared/scripts/checkout-server.sh airflow --with-source`로 소스를 추가합니다.
`check`, `render`, `deploy`는 준비된 이미지·chart·env와 배포 파일만 사용합니다.
이미지 자동 push는 하지 않으며, registry 또는 이미지 파일로 서버에 반입합니다.

## 서비스 의존성·경로 이전

Airflow 자체 실행에는 PostgreSQL이 필요하며, 업무 DAG에는 Portal API 및 설정된 외부 서비스 연결이 필요합니다.
이미지·DB·API 계약과 운영 PV·ODBC 절대 경로는 유지합니다.
기존 로컬 로그는 이관하지 않습니다. 새 로그 디렉터리는 초기화 서비스가 생성·권한 설정합니다.
기존 DB와 named volume은 초기화하지 않습니다. 이전 로그는 자동 삭제하지 않습니다.
