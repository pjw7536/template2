# Airflow 단일 서버 Kubernetes 배포

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

기존 Kubernetes 클러스터의 Worker 한 대에 Airflow와 내부 PostgreSQL을 배포하는 안내입니다.
처음 설치한다면 아래 01~04를 순서대로 읽고, 이미 운영 중이면 필요한 단계만 실행합니다.
문서 번호는 읽는 순서이며 스크립트 명령 이름과는 별개입니다.

## 상황별 시작점

| 상황 | 시작할 문서 |
| --- | --- |
| 처음 설치 | [01 서버 준비](01_SERVER_SETUP.md) → [02 환경변수](env/02_ENVIRONMENT.md) → [03 차트·이미지](03_ARTIFACTS.md) → [04 실행](04_SETUP_FLOW.md) |
| 입력과 이미지가 모두 준비됨 | [04 단계별 검사·배포·접속](04_SETUP_FLOW.md) |
| env·DB·URL·Secret 설정 확인 | [02 환경변수](env/02_ENVIRONMENT.md) |
| DAG·플러그인 이미지 갱신 | [05 업데이트](05_OPERATIONS.md#3-dag이미지-업데이트) |
| 기존 Compose DB 이전·백업 | [05 운영](05_OPERATIONS.md) |
| 배포·접속 실패 | [05 문제 해결](05_OPERATIONS.md#4-실패-단계-확인) |

## 현재 구성

| 항목 | 저장소 원본 기준 |
| --- | --- |
| chart / Airflow | Apache 공식 Helm chart 1.22.0 / Airflow 2.11.0 |
| 실행 방식 | LocalExecutor, Redis·Celery worker 없음 |
| DB | 기본 PostgreSQL 16 StatefulSet, external 모드 선택 가능 |
| 저장 | Worker local PV에 DB·로그 저장, Retain 정책 |
| DAG·플러그인 | 이미지에 포함, 변경 시 새 고유 태그로 빌드·배포 |
| 접속 | port-forward 또는 기존 공용 Traefik의 HTTPS `/airflow` |
| 기본 배포 명령 | `make airflow-check` → `make airflow-up` |

단일 Worker와 로컬 디스크에 의존하므로 고가용성 구성은 아닙니다.
DB 백업과 같은 시점의 env·Fernet 키를 다른 저장매체에도 보관합니다.

## 준비가 끝났을 때 실행

저장소 루트의 Bash에서 실행합니다. 이 두 명령은 최초 env·chart·이미지·디스크 준비를 대신하지 않습니다.

```bash
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

`airflow-check`는 설정·chart·클러스터 버전·노드·기존 비밀값을 검사합니다.
`airflow-up`은 Airflow를 배포하며 Ingress 사용 시 필요한 공용 Traefik 라우팅도 적용합니다.
Keycloak과 Keycloak DB는 재배포하지 않습니다. 신규 DAG는 일시정지로 생성하며 기존 DAG의 활성 상태는 유지합니다.
직접 `manage.py deploy`를 실행할 때는 [실행 방식의 차이](04_SETUP_FLOW.md#6-고급-직접-deploy와-helm-override)를 확인합니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `AIRFLOW_ENV=/절대경로/k8s.env` | Makefile 명령에 다른 env 전달 |
| `AIRFLOW_TLS_SOURCE=namespace/secret` | Airflow TLS Secret 최초 등록에 기존 인증서 사용 |
| `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` | 별도 위치의 chart 지정, 셸에서 export |

TLS 최초 등록 명령과 검사·배포별 영향은 [04 실행](04_SETUP_FLOW.md)에 있습니다.
기존 `make server-up`은 두 앱 통합 경로이며 Airflow 단독 배포에는 위 전용 명령을 사용합니다.

## Keycloak 로그인

[SSO 설정·client 등록·검증 안내](k8s/jobs/keycloak-client/README.md)를 따릅니다.
정상 로그인한 모든 사용자는 기본 Viewer이며 `airflow` client의 User·Admin만 추가 권한으로 적용합니다.
공개 env의 `AIRFLOW_AUTH_MODE=db`는 기존 배포 호환값입니다. 서버 전환 시 실제 OIDC 입력을 준비하고
`keycloak`으로 바꿔 배포합니다. 로컬은 실행 도구가 Keycloak 모드를 적용합니다.

## 파일과 설정 소유권

| 경로 | 역할 |
| --- | --- |
| [01_SERVER_SETUP.md](01_SERVER_SETUP.md) | 실행 호스트·Worker·도구·디스크 준비 |
| [env/02_ENVIRONMENT.md](env/02_ENVIRONMENT.md) | 키 초기화와 서버·DB·연동 입력 설명 |
| [03_ARTIFACTS.md](03_ARTIFACTS.md) | chart 확보, 이미지 빌드·전달, ODBC 준비 |
| [04_SETUP_FLOW.md](04_SETUP_FLOW.md) | 독립 실행 명령과 단계별 완료 기준 |
| [05_OPERATIONS.md](05_OPERATIONS.md) | 백업·이전·업데이트·장애 확인 |
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
[서버 선택 checkout](../SERVER_CHECKOUT.md)을 사용하고 외부 PC 개발은 [local 안내](../../local/README.md)를 따릅니다.
