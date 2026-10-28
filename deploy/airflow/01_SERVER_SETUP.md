# 01. Airflow 서버 준비

[시작 안내](README.md) · 다음: [환경변수](env/02_ENVIRONMENT.md)

Airflow를 처음 배포하거나 실행 Worker를 바꿀 때 읽습니다.
여기서는 클러스터와 디스크를 준비합니다. 실제 설치는 [04 단계별 실행](04_SETUP_FLOW.md)에서 진행합니다.

## 1. 실행 위치와 도구 확인

명령은 저장소 루트에서 실행합니다. 서버 선택 checkout은
[선택 체크아웃 안내](../SERVER_CHECKOUT.md)의 `airflow` 선택을 사용합니다.
기본 checkout은 `deploy/airflow`와 공통 도구·문서만 받습니다. 검사·렌더·배포에는 소스와 `local/`이 필요하지 않습니다.
서버 이미지 빌드가 필요하면 `bash deploy/shared/scripts/checkout-server.sh airflow --with-source`로 소스를 추가합니다.

기존 사내 Compose와 같은 이미지·패키지 설정이 `env/build.env`에 채워져 있습니다.
APT/PIP mirror, BigDataQuery Python·ODBC 설치 옵션, versioned driver URL을 다시 옮길 필요가 없습니다.

실행 호스트에는 Python 3.10 이상, Helm 3.19.0 이상, kubectl이 필요합니다.
chart가 요구하는 Kubernetes 최소 버전은 1.30.13입니다.
이 숫자는 도구의 최소 요구사항이며, 현재 사내 설치 버전이나 신규 설치 권장 버전을 뜻하지 않습니다.
사내 배포는 [현재 클러스터](../shared/docs/infrastructure/cluster.md)를 사용합니다. 빈 서버 구축은
[설치 기준 조회](../shared/docs/kubernetes/01-baseline.md) 후 확인된 도구·버전으로 준비합니다.
이 도구는 Kubernetes 자체나 Ingress controller를 설치하지 않습니다.
Ingress 없이도 port-forward로 UI에 접속할 수 있습니다.

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
```

다음 명령도 **저장소가 있는 실행 호스트**에서 수행합니다.

```bash
python3 --version
helm version --short
kubectl --context "$AIRFLOW_KUBE_CONTEXT" version
```

완료 기준: 선택한 context의 노드를 조회할 수 있고 도구·클러스터가 위 최소 버전을 충족해야 합니다.
`NODE_NAME`에는 노드 이름을 추측해서 넣지 말고 출력된 `kubernetes.io/hostname` 값을 사용합니다.
현재 `khplane01w09`는 [Keycloak 전용 Worker](../shared/docs/infrastructure/cluster.md#2026-10-27-worker-용도와-minio-배치-지정)입니다.
Airflow는 이 노드를 제외하고 자원·디스크·ODBC 접근을 확인한 Worker를 선택합니다.
`khplanew01`에는 MinIO 배치가 지정되어 있으므로 함께 실행할 여유 자원과 저장소를 먼저 확인합니다.
새 터미널에서는 context 변수를 다시 입력합니다.

## 2. 배포 설정 준비

[02 환경변수](env/02_ENVIRONMENT.md)에서 최초 키 생성 여부를 판단하고 서버 값을 입력합니다.
현재 설치는 새 DB이므로 기존 DB dump·계정·Fernet 키를 가져오지 않습니다.
설치 후 재배포할 때는 이번에 생성한 DB 비밀번호·Fernet 키를 유지합니다.
이후 디스크 경로·UID/GID는 입력한 env와 일치시켜야 합니다.

## 3. Worker의 디스크 준비

아래 명령은 kubectl 실행 호스트가 아니라 **NODE_NAME으로 선택한 Worker에 접속해서** 수행합니다.
아래 경로와 UID/GID는 예시 설정 기준이며 실제 env에 맞게 바꿉니다.
`POSTGRES_MODE=external`이면 아래 생성·검사 명령에서 PostgreSQL 경로를 제외합니다.

```bash
sudo install -d -o 999 -g 999 -m 0700 /srv/airflow/postgres
sudo install -d -o 50000 -g 0 -m 0770 /srv/airflow/logs
```

기존 Compose PostgreSQL 데이터 폴더를 바로 연결하지 않습니다.
데이터를 옮길 때는 [기존 DB 이전](05_OPERATIONS.md#2-기존-compose-db-이전)을 따릅니다.

local PV는 폴더를 자동으로 만들지 않습니다. 또한 20Gi 선언은 실제 파일시스템 사용량을 제한하지 않으므로
DB·로그 디스크의 여유 공간을 따로 감시해야 합니다.

로그는 기존 Compose와 같이 자동 삭제하지 않습니다.
자동 정리가 필요하면 보관 정책을 정한 뒤 `scheduler.logGroomerSidecar`를 설정합니다.

여러 Pod가 RWO 로그 PVC를 함께 쓰도록 같은 노드에 고정합니다.
Airflow와 내부 DB가 한 Worker에 있으므로 해당 Worker나 디스크에 장애가 나면 Airflow가 중단됩니다.

```bash
df -h /srv/airflow/postgres /srv/airflow/logs
sudo stat -c '%U:%G %a %n' /srv/airflow/postgres /srv/airflow/logs
```

`POSTGRES_MODE=external`이면 내부 DB 디렉터리는 준비하지 않고 로그 디렉터리만 준비합니다.
외부 DB는 미리 생성한 DB·계정으로 Worker에서 접근할 수 있어야 합니다.
ODBC 파일 준비는 [03 차트·이미지](03_ARTIFACTS.md#3-odbc-설정-준비)를 따릅니다.

완료 기준: env에 지정한 Worker에 DB·로그 경로가 있고 컨테이너 UID/GID가 쓸 수 있어야 합니다.
local PV의 용량 선언과 실제 디스크 여유 공간은 별도로 확인합니다.

## 4. 다음 단계

[03 차트·이미지](03_ARTIFACTS.md)를 준비한 뒤 [04 단계별 실행](04_SETUP_FLOW.md)으로 이동합니다.
이미 준비된 서버에 DAG만 갱신할 때는 [05 운영](05_OPERATIONS.md)의 업데이트 순서를 사용합니다.
