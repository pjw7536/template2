# Airflow 단일 서버 Kubernetes 배포

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

기존 Kubernetes 클러스터에서 선택한 Worker 한 대에 Airflow와 내부 PostgreSQL을 함께 실행합니다.
Airflow는 Apache 공식 Helm chart **1.22.0**, 실행 이미지는 기존 **Airflow 2.11.0**,
Executor는 **LocalExecutor**입니다. Redis·Celery worker·외부 DB 서버는 사용하지 않습니다.
DAG와 관리자 초기화 코드는 이미지에 포함하고, DB와 로그는 같은 노드의 영구 디스크에 저장합니다.

앱별 배포는 최초 입력 준비 후 `make airflow-check KUBE_CONTEXT=<context>`와
`make airflow-up KUBE_CONTEXT=<context>`를 순서대로 실행합니다.
Airflow 리소스와 필요한 공용 Traefik 라우팅·TLS 연결만 적용하며 Keycloak·Keycloak DB를 재배포하지 않습니다.
신규 DAG는 일시정지로 생성합니다. 기존 Airflow DB의 활성 DAG는 그대로 유지합니다.
`AIRFLOW_ENV=/절대경로/k8s.env`, `AIRFLOW_TLS_SOURCE=namespace/secret`으로 입력을 지정할 수 있습니다.
Ingress가 활성화되면 기존 `etch-sso/traefik`이 필요하며, 비활성화하면 단독 배포 후 port-forward를 사용합니다.
Ingress 없는 `airflow-check`는 설정·차트 렌더만 검사하고 클러스터 준비 검사는 배포 때 수행합니다.
기존 두 앱 통합 명령 `make server-up`은 호환용으로 유지합니다.
아래 단독 `manage.py deploy`는 기존 Compose와 같은 일반 실행 기본값을 사용합니다.

## 파일과 설정 소유권

외부 PostgreSQL을 사용할 때는 `POSTGRES_MODE=external`과 `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PASSWORD`를 지정합니다. 이 모드에서는 DB workload·DB PV를
생성하거나 내부 StatefulSet을 기다리지 않습니다. 로그 PV는 유지합니다. DB와 계정·네트워크는 먼저 준비합니다.
새 DB 전환 시 기존 DB를 자동 이전하거나 삭제하지 않습니다. 기존 env에서 새 키를 생략하면 internal 기본값을 유지합니다.
`--values /경로/values.yaml`로 환경별 비밀값 없는 Helm override를 추가할 수 있습니다.

| 경로 | 역할 |
| --- | --- |
| `helm/chart.lock.json` | 공식 chart 버전·다운로드 주소·SHA-256·최소 도구 버전 |
| `helm/values.yaml` | Executor·자원·Secret 참조·로그·마이그레이션 설정 |
| `k8s/postgres/stack.json` | PostgreSQL 16 StatefulSet·내부 Service |
| `k8s/storage/volumes.json` | DB·로그 local PV/PVC, Retain 정책·노드 고정 |
| `env/k8s.env.example` | 서버별 설정과 Secret 입력 예시 |
| `env/build.env.example` | 기본 이미지·사내 패키지 mirror·ODBC 빌드 입력 |
| `../../apps/airflow/image/Dockerfile` | DAG·플러그인·관리자 초기화가 포함된 최종 이미지 |
| `scripts/manage.py` | 초기 설정·차트 확보·이미지 빌드·검사·렌더·배포 |

실제 `env/k8s.env`, `env/build.env`, `helm/vendor/`, `rendered/`, `backups/`는 Git에서 제외합니다.
Kubernetes 배포는 `k8s.env`를 읽습니다.
DAG·플러그인·Dockerfile 원본은 [apps/airflow](../../apps/airflow/README.md)가 소유합니다.
외부 PC용 Kubernetes 개발 설정은 [local/](../../local/README.md)에서 관리합니다.

## 1. 서버와 도구 준비

명령은 저장소 루트에서 실행합니다. 서버 선택 checkout은
[선택 체크아웃 안내](../SERVER_CHECKOUT.md)의 `airflow` 선택을 사용합니다.
기본 checkout은 `deploy/airflow`와 공통 도구·문서만 받습니다. 검사·렌더·배포에는 소스와 `local/`이 필요하지 않습니다.
서버 이미지 빌드가 필요하면 `bash deploy/shared/scripts/checkout-server.sh airflow --with-source`로 소스를 추가합니다.

기존 사내 Compose와 같은 이미지·패키지 설정이 `env/build.env.example`에 채워져 있습니다.
APT/PIP mirror, BigDataQuery Python·ODBC 설치 옵션, versioned driver URL을 다시 옮길 필요가 없습니다.

필요 도구는 **Python 3.10+**, **Helm 3.19.0+**, kubectl이며,
Kubernetes는 chart 요구사항상 **1.30.13 이상**이어야 합니다. 이는 현재 사내 설치 버전 확인값이나 신규 설치 권장 버전이 아닙니다.
사내 배포는 [현재 클러스터](../shared/docs/infrastructure/cluster.md)를 사용합니다. 빈 서버 구축은
[설치 기준 조회](../shared/docs/kubernetes/01-baseline.md) 후 확인된 도구·버전으로 준비합니다.
이 도구는 Kubernetes 자체나 Ingress controller를 설치하지 않습니다.
Ingress 없이도 port-forward로 UI에 접속할 수 있습니다.

```bash
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
python3 deploy/airflow/scripts/manage.py init-secrets
cp deploy/airflow/env/build.env.example deploy/airflow/env/build.env
```

`init-secrets`는 파일을 0600 권한으로 만들고 DB 비밀번호·관리자 비밀번호·Fernet 키·웹서버 키를 생성합니다.
기존 파일이 있으면 덮어쓰지 않습니다. 다음 값을 실제 환경에 맞게 편집합니다.

- `NODE_NAME`: 노드의 `kubernetes.io/hostname` label 값. 모든 Airflow Pod·DB·PV가 이 노드에 묶입니다.
- `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`: 배포할 DAG 포함 이미지. 매 배포마다 고유 태그를 사용합니다.
- `POSTGRES_IMAGE`: 기존 사내 PostgreSQL 16 이미지 주소가 기본 입력되어 있습니다. mirror가 바뀐 경우에만 수정합니다.
- `POSTGRES_UID`, `POSTGRES_GID`: 해당 이미지 사용자 UID/GID. 공식 Debian 이미지 기본값은 999/999입니다.
- `ODBC_HOST_PATH`: 서버의 ODBC 설정 디렉터리 절대 경로. 기본 예시는 `/srv/airflow/odbc`입니다.
- `AIRFLOW_ADMIN_EMAIL`: 실제 관리자 이메일. 생성된 관리자 비밀번호는 이 파일에서 확인합니다.
- `AIRFLOW_API_BASE_URL`: Airflow DAG가 호출하는 Portal API 주소. 다른 namespace라면 Service DNS를 수정합니다.
- `AIRFLOW_TRIGGER_TOKEN`: Portal API의 동일 변수와 일치시키며 새로 임의 생성하지 않습니다.
- `AIRFLOW_WEBSERVER_BASE_URL`: `/airflow`로 끝나는 접속 URL. 기본값은 port-forward 주소입니다.

Knox 연결과 실패 알림이 필요하면 같은 파일의 `KNOX_*`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS`를 채웁니다.
설정은 따옴표 없이 `KEY=값`으로 작성하며 `$VAR`, `$(...)`를 실행하거나 확장하지 않습니다.
서버 외부에 설정을 보관할 경우 모든 명령에 `--env /절대경로/k8s.env`를 사용할 수 있습니다.

서버에서 디스크 디렉터리를 준비합니다. 아래 경로와 UID/GID는 예시 설정 기준입니다.

```bash
sudo install -d -o 999 -g 999 -m 0700 /srv/airflow/postgres
sudo install -d -o 50000 -g 0 -m 0770 /srv/airflow/logs
```

기존 Compose PostgreSQL 데이터 디렉터리를 바로 연결하지 마세요. 이전은 아래 절차를 따릅니다.
local PV는 디렉터리를 자동 생성하지 않으며 20Gi 선언은 파일시스템 사용량 제한을 보장하지 않습니다.
DB·로그 디스크 여유 공간을 감시해야 합니다. 기존 Compose와 같이 로그를 자동 삭제하지 않습니다.
자동 정리가 필요하면 운영 보관 정책을 정한 뒤 `scheduler.logGroomerSidecar`를 설정합니다.
RWO 로그 PVC를 여러 Pod가 공유할 수 있도록 모두 같은 노드에 고정했습니다.
Airflow와 내부 DB가 한 Worker에 묶이므로 해당 Worker·디스크 장애 시 Airflow가 중단됩니다.

## 2. 공식 chart 준비

인터넷에 연결된 환경에서는 다음 명령으로 checksum까지 확인합니다.

```bash
python3 deploy/airflow/scripts/manage.py fetch-chart
```

사내망이 외부에 연결되지 않으면 외부 PC에서 받은
`deploy/airflow/helm/vendor/airflow-1.22.0.tgz`를 서버의 같은 위치로 반입합니다.
다른 위치의 파일은 `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` 환경변수로 지정합니다.
검사·렌더·배포는 차트를 자동 다운로드하지 않으며 고정 SHA-256이 다르면 중단합니다.
차트 dependency도 압축 파일에 포함되어 있어 `helm dependency update`가 필요하지 않습니다.

## 3. DAG 포함 이미지 준비

`env/build.env.example`을 복사하면 사내 의존성 이미지의 build arg가 적용됩니다.
사내 base image·APT/PIP mirror·trusted hosts·ODBC artifact URL이 동일하며
`INSTALL_BIGDATAQUERY_PYTHON=true`, `INSTALL_BIGDATAQUERY_ODBC=true`가 기본값입니다.
기존에 공개 기본값으로 만든 `build.env`가 있으면 예시와 비교해 이 값을 갱신합니다.
사내 주소는 env에서 변경할 수 있으며 Dockerfile·배포 Python 코드에는 고정하지 않습니다.
빌드 인자에는 비밀번호·접근 토큰을 넣지 않습니다.

```bash
python3 deploy/airflow/scripts/manage.py build-image \
  --build-env deploy/airflow/env/build.env
```

Docker가 있는 빌드 환경에서 실행합니다. 기존 `apps/airflow/image/Dockerfile.dependencies`로 의존성 이미지를 만들고
`apps/airflow/image/Dockerfile`로 DAG·플러그인을 추가합니다. 최종 context는 `apps/airflow`입니다. 빌드 context에 실제 env·로그·DSN은 보내지 않습니다.
이미지는 자동 push하지 않습니다. `k8s.env`에 지정한 이미지 이름으로 `docker push`하거나,
`docker save` 후 서버 containerd에 반입하세요. K3s이면 `sudo k3s ctr images import <이미지.tar>`를 사용합니다.
**Docker에만 이미지가 있어서는 Kubernetes가 사용할 수 없습니다.** PostgreSQL 이미지도 준비합니다.
DAG 변경 시 이미지를 다시 빌드하고 `AIRFLOW_IMAGE_TAG`를 변경해 재배포합니다.
플러그인 소스는 `apps/airflow/plugins`에 두며 최종 이미지에 함께 포함됩니다.

private registry 인증이 필요하면 대상 namespace에 imagePullSecret을 미리 만들고
`IMAGE_PULL_SECRET`에 이름을 입력합니다.

ODBC 기본 방식은 기존 디렉터리 전체를 같은 노드에서 읽기 전용으로 마운트하는 방식입니다.
`ODBC_HOST_PATH`를 기존 서버 ODBC 설정 디렉터리의 절대 경로로 지정하면 INI·인증서·하위 파일을 그대로 사용합니다.
새 서버라면 기존 디렉터리 전체를 `/srv/airflow/odbc`로 복사하고 Airflow UID 50000이 읽을 수 있게 권한을 유지합니다.
이 저장소에는 실제 DSN·인증서가 없으므로 빈 파일을 생성해서 대신하지 않습니다.
경로가 없으면 Kubernetes가 Pod 기동을 차단합니다. 단일 서버에 고정하므로 다른 노드의 파일을 참조하지 않습니다.

| 기존 컨테이너 설정 | Kubernetes 유지 값 |
| --- | --- |
| ODBC 디렉터리 | `/usr/local/odbc`, 전체 디렉터리 읽기 전용 |
| `ODBCINI` | `/usr/local/odbc/odbc.ini` |
| `ODBCSYSINI` | `/usr/local/odbc` |
| `CLOUDERAIMPALAINI` | `/etc/cloudera.impalaodbc.ini`, 기존 드라이버 이미지에서 상속 |

Secret 방식을 사용하려면 `ODBC_HOST_PATH=`로 비우고 기존 namespace Secret 이름을
`ODBC_SECRET_NAME`에 지정합니다. 두 방식을 동시에 지정하면 설정 검사에서 중단합니다.
namespace는 `kubectl --context "$AIRFLOW_KUBE_CONTEXT" create namespace airflow`로 미리 만들 수 있습니다.

## 4. 검사와 렌더

```bash
# 공개 예시와 실제 차트 검사: 클러스터에 연결하지 않습니다.
make server-check APP=airflow

# 실제 설정의 누락·예시값·URL·키 형식 검사와 렌더 검증
python3 deploy/airflow/scripts/manage.py check --env deploy/airflow/env/k8s.env

# 검토할 manifest와 Helm overlay 생성: Secret 값은 포함하지 않습니다.
python3 deploy/airflow/scripts/manage.py render \
  --env deploy/airflow/env/k8s.env --output deploy/airflow/rendered
```

출력 `airflow.yaml`은 검토용입니다. 그대로 `kubectl apply`하지 말고 아래 deploy 명령을 사용하세요.
Helm hook으로 DB migration과 관리자 생성 순서를 관리해야 합니다.
`check` 통과는 이미지 pull·디스크 권한·실제 Portal 연결 성공까지 보장하지 않습니다.

## 5. 배포와 접속

```bash
python3 deploy/airflow/scripts/manage.py deploy \
  --env deploy/airflow/env/k8s.env --context "$AIRFLOW_KUBE_CONTEXT"
```

대상 context를 반드시 명시합니다. 도구는 서버 버전·노드 Ready 상태·Secret 참조를 확인하고
namespace → Secret → local PV/PVC → PostgreSQL 준비 → Helm migration·관리자 생성 → Airflow 준비 순서로 실행합니다.
관리자 계정은 없을 때만 생성하고 기존 계정의 비밀번호·역할은 변경하지 않습니다.
DB 비밀번호와 Fernet 키가 기존 Secret과 다르면 중단합니다. 키 교체는 별도 운영 절차로 수행합니다.
다른 runtime Secret 변경은 배포 마지막에 Pod를 재시작해 반영합니다.

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow port-forward svc/airflow-webserver 8080:8080
```

같은 컴퓨터에서 `http://localhost:8080/airflow`에 접속합니다. 원격 PC에서는 SSH 터널을 사용합니다.
Ingress를 사용할 때는 기존 controller의 `INGRESS_CLASS_NAME`, 실제 URL,
HTTPS 인증서 Secret인 `INGRESS_TLS_SECRET`을 설정하고 `INGRESS_ENABLED=true`로 재배포합니다.
Ingress는 `/airflow` 접두사를 유지하며 rewrite하지 않습니다. DNS는 서버의 Ingress 주소를 가리켜야 합니다.

**기존 Compose처럼 신규 DAG는 활성 상태로 생성됩니다.** 배포 전에 기존 scheduler를 중지하고
Portal API 연결·trigger token을 준비합니다. 기존 DB에서 복원한 DAG의 일시정지 상태는 그대로 유지됩니다.
이전 작업 중 신규 DAG 자동 실행을 막아야 한다면 배포 전에 `helm/values.yaml`의
`config.core.dags_are_paused_at_creation`을 `True`로 설정하고 전환 후 필요한 DAG를 활성화합니다.
Portal에서 Airflow REST API를 호출한다면 Portal 쪽 내부 URL인
`http://airflow-webserver.airflow.svc.cluster.local:8080/airflow`을
`AIRFLOW_BASE_URL`에 설정하고 `AIRFLOW_USERNAME`·`AIRFLOW_PASSWORD`도 Airflow 계정과 일치시킵니다.
브라우저 링크는 `AIRFLOW_PUBLIC_BASE_URL`에 설정합니다. namespace를 변경했다면 DNS도 수정합니다.

자원 기본값은 `helm/values.yaml`과 `k8s/postgres/stack.json`에 명시했습니다.
Airflow 2.11.0의 기존 기본값과 동일하게 parallelism=32, DAG별 task=16·run=16,
웹서버 worker=4를 유지합니다. 초기화 Job은 기존 `airflow-init`와 같이 `default_pool` slots를 -1로 설정합니다.
CPU·메모리 제한은 Kubernetes 운영값이므로 실제 작업량과 서버 사양에 맞춰 조정합니다.
리소스 제한이 없는 기존 Compose와 처리 용량까지 같다는 의미는 아닙니다.

## 6. 백업·기존 데이터 이전·업데이트

PostgreSQL은 Airflow Helm release 밖에서 관리하므로 `helm uninstall airflow`가 DB를 삭제하지 않습니다.
PV는 Retain이며 namespace나 PVC 삭제 후 자동 재연결되지 않습니다. 정상 업데이트에서는 삭제하지 마세요.
Fernet 키를 잃으면 기존 Connection·Variable의 암호화된 값을 복호화하지 못합니다.
실제 `k8s.env`도 접근을 제한해 백업합니다.

DB 백업은 운영자가 정한 주기에 실행합니다. 아래 예시는 실행 시각별 custom-format dump를 만들며
실패한 백업은 완료 파일로 남기지 않습니다. 비밀번호는 컨테이너의 기존 Secret 환경에서 읽습니다.

```bash
mkdir -p deploy/airflow/backups
chmod 700 deploy/airflow/backups
(
  set -eu
  umask 077
  backup_file="deploy/airflow/backups/airflow-$(date +%Y%m%d-%H%M%S).dump"
  kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow exec airflow-postgres-0 -- \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U airflow -d airflow -Fc' \
    > "$backup_file.partial"
  mv "$backup_file.partial" "$backup_file"
)
```

백업 사본을 다른 저장매체에 보관하세요. 같은 서버·디스크에만 두면 디스크 장애를 복구할 수 없습니다.

기존 Compose DB를 이전한다면 다음 순서를 지킵니다.

1. 기존 DAG를 일시정지하고 실행 중인 작업을 종료·완료시킨 후 기존 scheduler/webserver를 중지합니다.
2. 기존 PostgreSQL 16에서 `pg_dump -Fc`로 백업하고 기존 Fernet 키·Connection·Variable을 확인합니다.
3. 새 서버 설정에 기존 Fernet 키를 입력하고 새 이미지·차트·디스크를 준비한 뒤 render/check를 실행합니다.
4. 전용 namespace와 `airflow-postgres` Secret(password 키)을 먼저 만들고 렌더된 `storage.json`, `postgres.json`만 적용합니다.
   Secret은 접근 제한된 파일에서 등록하고 `k8s.env`의 DB 비밀번호와 일치시킵니다.
5. 새 DB가 준비되면 **비어 있는 새 airflow DB에만** `pg_restore --no-owner --no-acl -U airflow -d airflow`로 복원합니다.
   기존 업무 DB를 덮어쓰지 않습니다. 필요하면 기존 로그도 새 로그 경로에 복사하고 50000:0 권한을 맞춥니다.
6. deploy를 실행해 공식 chart migration을 적용합니다. 기존 계정이 있으면 그대로 사용하며 자동 비밀번호 초기화는 하지 않습니다.
7. Portal 연결·기존 Connection 복호화·DAG 상태를 확인하고 하나의 scheduler만 작업을 실행하도록 활성화합니다.

업데이트 전 DAG를 일시정지하고 실행 중인 작업이 끝난 뒤 DB를 백업하고 새 이미지 태그를 지정합니다.
업데이트 완료 후 필요한 DAG를 다시 활성화합니다. 공식 chart의 post-install migration hook과
Pod의 migration 대기가 교착하지 않도록 배포 스크립트는 Helm `--wait`·`--atomic`을 사용하지 않고
hook 완료 후 별도로 rollout을 확인합니다. 실패 시 자동 삭제·DB rollback은 수행하지 않습니다.
Helm rollback으로 DB schema까지 되돌아가지는 않으므로 DB 복원은 해당 버전의 절차로 수행합니다.
이번 구성은 기존 2.11.0 배포 전환용이며 Airflow 3 업그레이드는 DAG·API·인증 호환성 검증을 별도로 진행합니다.

## 공식 참고

- [Apache Airflow Helm chart와 요구사항](https://airflow.apache.org/docs/helm-chart/stable/index.html)
- [운영 DB·Secret·이미지 구성](https://airflow.apache.org/docs/helm-chart/stable/production-guide.html)
- [DAG 이미지 배포](https://airflow.apache.org/docs/helm-chart/stable/manage-dag-files.html)
- [로그 영구 저장](https://airflow.apache.org/docs/helm-chart/stable/manage-logs.html)

공식 문서는 운영 DB를 별도로 관리하도록 권장합니다. 이 저장소는 서버 한 대 조건에 맞춰
같은 Kubernetes 노드에서 PostgreSQL을 별도 StatefulSet으로 관리하며 고가용성을 제공하지 않습니다.
