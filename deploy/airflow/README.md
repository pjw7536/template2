# Airflow 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

기존 Kubernetes 클러스터의 Worker 한 대에 Airflow와 PostgreSQL을 설치합니다.
기본 Keycloak 로그인을 사용하려면 Keycloak의 사내 로그인 준비와 전용 client 등록이 필요합니다.
최초 설치는 새 DB·전용 계정·Fernet 키를 준비하고, 재배포는 기존 DB 비밀번호와 Fernet 키를 유지합니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업 | 완료 기준 |
| --- | --- | --- |
| 1 | [서버·Worker 준비](docs/01-setup.md) | 도구·클러스터 버전과 디스크·쓰기 권한 확인 |
| 2 | [환경설정](docs/02-environment.md) | 실제 env·DB·키·공개 URL 준비 |
| 3 | [chart·이미지·ODBC 준비](docs/03-artifacts.md) | 고정 chart와 Worker에서 사용할 이미지·ODBC 파일 준비 |
| 4 | [Keycloak client 등록](docs/04-sso.md) | client secret·redirect URI·역할 설정 확인 |
| 5 | [검사·배포·검증](docs/05-deploy.md) | DB·scheduler health와 UI 로그인·필요 연동 확인 |

실행 위치는 각 절차에서 확인합니다. 관리 호스트와 실제 데이터를 저장하는 Worker를 구분합니다.
이미 준비된 서버는 [검사·배포](docs/05-deploy.md)부터 진행하고, 새 터미널에서는 context와 env 입력을 다시 준비합니다.

## 운영·변경 작업

| 하려는 일 | 문서 |
| --- | --- |
| DAG·이미지 갱신 | [업데이트](docs/06-operations.md#3-dag이미지-업데이트) |
| DB·설정 백업과 기존 DB 이전 | [운영 안내](docs/06-operations.md) |
| 배포 실패·접속 실패 | [실패 단계 확인](docs/06-operations.md#4-실패-단계-확인) |
| 로그인 방식·역할 확인 | [로그인 입력](docs/02-environment.md#keycloak-로그인) |

## 현재 구성

| 항목 | 저장소 원본 기준 |
| --- | --- |
| chart / Airflow | Apache 공식 Helm chart 1.22.0 / Airflow 3.3.2 |
| 구성 요소 | API server·scheduler·독립 DAG processor·triggerer |
| 실행 방식 | LocalExecutor, Redis·Celery worker 없음 |
| DB | 기본 PostgreSQL 16 StatefulSet, external 모드 선택 가능 |
| 저장 | Worker local PV에 DB·로그 저장, Retain 정책 |
| DAG·플러그인 | 이미지에 포함, 변경 시 새 고유 태그로 빌드·배포 |
| 접속 | port-forward 또는 기존 공용 Traefik의 HTTPS `/airflow` |
| 기본 배포 명령 | `make airflow-check` → `make airflow-up` |

단일 Worker와 로컬 디스크에 의존하므로 고가용성 구성은 아닙니다.
DB 백업과 같은 시점의 env·Fernet 키를 다른 저장매체에도 보관합니다.

## 파일과 설정 소유권

| 경로 | 역할 |
| --- | --- |
| [docs/01-setup.md](docs/01-setup.md) | 실행 호스트·Worker·도구·디스크 준비 |
| [docs/02-environment.md](docs/02-environment.md) | 키 초기화와 서버·DB·연동 입력 설명 |
| [docs/03-artifacts.md](docs/03-artifacts.md) | chart 확보, 이미지 빌드·전달, ODBC 준비 |
| [docs/04-sso.md](docs/04-sso.md) | Keycloak 전용 client·역할 등록과 로그인·API 검증 |
| [docs/05-deploy.md](docs/05-deploy.md) | 독립 실행 명령과 단계별 완료 기준 |
| [docs/06-operations.md](docs/06-operations.md) | 백업·이전·업데이트·장애 확인 |
| `helm/chart.lock.json` | 고정 chart 버전·주소·SHA-256·최소 도구 버전 |
| `helm/values.yaml` | Executor·자원·Secret 참조·로그·migration 설정 |
| `k8s/postgres/stack.json` | 내부 PostgreSQL StatefulSet·Service |
| `k8s/storage/volumes.json` | local PV/PVC·Retain 정책·노드 고정 |
| `env/k8s.env` | 서버별 설정과 Secret 입력 |
| `env/build.env` | 기본 이미지·패키지 mirror·ODBC 빌드 입력 |
| `scripts/manage.py` | 초기 설정·chart 확보·빌드·검사·렌더·직접 배포 |
| `scripts/up.py` | Makefile의 Airflow 검사·배포 진입점 |

DAG·플러그인·Dockerfile은 [apps/airflow](../../apps/airflow/README.md)가 소유합니다.
서버 검사·렌더·배포는 앱 소스와 local 파일 없이 실행할 수 있으며 이미지 빌드에만 앱 소스가 필요합니다.
[서버 선택 checkout](../shared/docs/operations/checkout.md)을 사용하고 외부 PC 개발은 [local 안내](../../local/README.md)를 따릅니다.
