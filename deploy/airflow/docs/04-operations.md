# Airflow 백업·이전·업데이트와 문제 해결

[앱 안내](../README.md) · 이전: [배포와 검증](03-deploy.md#배포와-검증)

**목적:** 설치 후 백업·Secret 복원·DB 이전·이미지 업데이트·장애 확인을 수행합니다. 최초 설치는 [서버 준비](01-prepare.md#서버-준비)부터 진행합니다.
**실행 위치:** 저장소 루트. 서버 context는 `kubernetes-admin@kubernetes`이며 다른 context를 쓰면 명령의 이름을 바꿉니다.
DB 명령은 `POSTGRES_MODE=internal`, namespace·DB·사용자 `airflow` 기준입니다. 외부 DB는 해당 DB 운영 절차로 백업·복원하고 내부 StatefulSet 명령을 사용하지 않습니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow get pods
```

## 1. DB와 설정 백업

DB와 **`k8s.env` 전체를 같은 시점의 백업으로 보관**합니다. env에는 Fernet 키와 DB 비밀번호가 있으며,
Fernet 키를 잃으면 기존 Connection·Variable의 암호화된 값을 읽을 수 없습니다.

PostgreSQL은 Airflow Helm release와 별도로 관리하므로 `helm uninstall airflow`가 DB를 삭제하지 않습니다.
PV 정책은 Retain이며 namespace나 PVC를 삭제해도 자동으로 다시 연결되지 않습니다. 정상 업데이트에서는 이 리소스를 삭제하지 않습니다.

운영자가 정한 주기에 실행합니다. 실행 시각별 custom-format dump를 만들고 실패한 백업은 완료 파일로 남기지 않으며, 비밀번호는 컨테이너의 기존 Secret 환경에서 읽습니다.

```bash
mkdir -p deploy/airflow/backups
chmod 700 deploy/airflow/backups
(
  set -eu
  umask 077
  backup_file="deploy/airflow/backups/airflow-$(date +%Y%m%d-%H%M%S).dump"
  kubectl --context kubernetes-admin@kubernetes -n airflow exec airflow-postgres-0 -- \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U airflow -d airflow -Fc' \
    > "$backup_file.partial"
  mv "$backup_file.partial" "$backup_file"
)
```

**기대 결과:** `deploy/airflow/backups/airflow-<시각>.dump`가 생성됩니다. 사본은 다른 저장매체에 보관합니다. 같은 서버·디스크에만 두면 디스크 장애를 복구할 수 없습니다.

## 2. Secret 복원

**사용 조건:** 사전 검사가 다음 이유로 중단된 경우입니다.

- 기존 DB PVC, `airflow-metadata` Secret 또는 scheduler·API server·DAG processor·triggerer Deployment가 남아 있는데 `airflow-fernet`이 없음
- 기존 `airflow-postgres` PVC가 있는데 `airflow-postgres` Secret이 없음

**준비물:** DB 백업 시점의 원래 Fernet 키와 실제 DB 비밀번호. 새 키를 생성하지 않으며 `init-secrets`를 다시 실행해 해결하지 않습니다.
같은 값이 env의 `AIRFLOW_FERNET_KEY`·`POSTGRES_PASSWORD`에도 있어야 합니다. 이미 Secret이 있으면 그 값과 env가 일치해야 합니다.
외부 DB만 남고 클러스터의 설치 흔적이 모두 사라진 환경은 자동으로 판별할 수 없으므로 DB 백업과 함께 보관한 원래 Fernet 키·env를 복원합니다.

비밀값이 명령행·로그에 남지 않도록 숨김 입력을 접근 제한 임시 파일로 전달합니다. 줄바꿈 없이 저장해야 env 값과 일치합니다.

```bash
(
  set -euo pipefail
  umask 077
  secret_file=$(mktemp)
  trap 'rm -f "$secret_file"' EXIT
  read -r -s -p '원래 Fernet 키: ' airflow_secret_value; printf '\n'
  test -n "$airflow_secret_value"
  printf '%s' "$airflow_secret_value" > "$secret_file"
  unset airflow_secret_value
  kubectl --context kubernetes-admin@kubernetes -n airflow create secret generic airflow-fernet \
    --from-file=fernet-key="$secret_file"
)
```

DB 비밀번호는 같은 블록에서 프롬프트를 `실제 DB 비밀번호`로, 마지막 명령을 다음으로 바꿔 실행합니다.

```bash
  kubectl --context kubernetes-admin@kubernetes -n airflow create secret generic airflow-postgres \
    --from-file=password="$secret_file"
```

**기대 결과:** `secret/airflow-fernet created` 또는 `secret/airflow-postgres created`. 이어서 `make airflow-check`를 다시 실행해 env와의 일치를 확인합니다.
`AlreadyExists`이면 기존 Secret이 있으므로 덮어쓰지 말고 env 값을 기존 값과 대조합니다.

## 3. 기존 Compose DB 이전

이 절은 DB 이전이 별도로 결정된 환경에만 적용하며 신규 설치에는 사용하지 않습니다.

1. 기존 DAG를 일시정지하고 실행 중인 작업을 종료·완료시킨 후 기존 scheduler/webserver를 중지합니다.
2. 기존 PostgreSQL 16에서 `pg_dump -Fc`로 백업하고 기존 Fernet 키·Connection·Variable을 확인합니다.
3. 새 서버 env에 기존 Fernet 키를 입력하고 새 이미지·chart·디스크를 준비한 뒤 render/check를 실행합니다.
4. 전용 namespace와 `airflow-postgres` Secret(`password` 키)을 [Secret 복원](#2-secret-복원)의 명령으로 먼저 만들고, 렌더된 `storage.json`, `postgres.json`만 적용합니다. 값은 `k8s.env`의 DB 비밀번호와 일치시킵니다.
5. 새 DB가 준비되면 **비어 있는 새 airflow DB에만** `pg_restore --no-owner --no-acl -U airflow -d airflow`로 복원합니다.
   기존 업무 DB를 덮어쓰지 않습니다. 필요하면 기존 로그도 새 로그 경로에 복사하고 50000:0 권한을 맞춥니다.
6. 배포를 실행해 공식 chart migration을 적용합니다. 기존 계정은 그대로 사용하며 비밀번호를 자동 초기화하지 않습니다.
7. Portal 연결·기존 Connection 복호화·DAG 상태를 확인하고 하나의 scheduler만 작업을 실행하도록 활성화합니다.

## 4. DAG·이미지 업데이트

### 공유 폴더 전환

Airflow는 워커의 `DAGS_HOST_PATH`를 `airflow-dags` PVC로 공유해 `/opt/airflow/dags`에서 읽습니다. 공유 폴더를 처음 연결하기 전에 기존 DAG를 일시정지하고 실행 중인 작업을 완료한 뒤 [DB를 백업](#1-db와-설정-백업)합니다.

1. CP1에서 현재 DAG Processor의 파일을 백업합니다. 최초 설치라면 새로 빌드한 Airflow 이미지의 `/opt/airflow/dags`를 같은 구조의 tar 파일로 준비합니다.

   ```bash
   (
     set -eu
     umask 077
     backup_dir="$HOME/airflow-backups"
     mkdir -p "$backup_dir"
     archive="$backup_dir/dags-$(date +%Y%m%d-%H%M%S).tar"
     kubectl --context kubernetes-admin@kubernetes -n airflow \
       exec deployment/airflow-dag-processor -c dag-processor -- \
       tar --exclude=__pycache__ -C /opt/airflow/dags -cf - . > "$archive.partial"
     tar -tf "$archive.partial" >/dev/null
     mv "$archive.partial" "$archive"
     printf '%s\n' "$archive"
   )
   ```

2. 완료된 tar를 `NODE_NAME` 워커에 반입합니다. 해당 워커에서 tar를 실제 경로로 지정한 뒤 아래를 실행합니다. 대상 디렉터리에 파일이 이미 있으면 우선 보존합니다. 전환과 함께 업데이트할 DAG 파일은 **준비 표식을 만들기 전에** 필요한 버전으로 복사합니다.

   ```bash
   read -r -p 'DAG 백업 tar 절대 경로: ' AIRFLOW_DAG_ARCHIVE
   sudo install -d -o root -g root -m 0755 /appdata/airflow/dags
   sudo tar --extract --skip-old-files --no-same-owner --no-same-permissions \
     --file "$AIRFLOW_DAG_ARCHIVE" --directory /appdata/airflow/dags
   ls -la /appdata/airflow/dags
   ```

3. DAG와 공통 Python 파일을 옮겼고 Airflow가 읽을 수 있는지 확인한 뒤 준비 표식을 만듭니다. `DAGS_HOST_PATH`를 실제 경로로 설정하고 CP1에서 [배포 검사·반영](#검사와-배포)을 진행합니다. 스케줄러와 DAG Processor는 준비 표식이 있는 볼륨에서 시작합니다.

   ```bash
   sudo install -o root -g root -m 0644 /dev/null /appdata/airflow/dags/.airflow-dags-initialized
   ```

4. `airflow-dags` PVC가 `Bound`이고 스케줄러·DAG Processor가 `Ready`인지 확인합니다. UI에서 기존 업무 DAG 목록과 import 오류를 확인한 뒤 테스트할 DAG를 활성화합니다. 문제가 있으면 `DAGS_HOST_PATH`를 비우고 이전 이미지 태그로 검사·배포해 이미지 기반으로 복구합니다. 공유 경로의 파일과 PV/PVC는 복구용으로 보관합니다.

### DAG 파일 추가·수정·삭제

워커의 `DAGS_HOST_PATH`에서 파일을 관리합니다. 추가·수정은 같은 디렉터리의 `.tmp` 파일에 복사한 뒤 최종 `.py` 이름으로 이동합니다. 삭제·교체는 DAG를 일시정지하고 실행 중인 작업이 끝난 뒤 합니다. Airflow가 다음 스캔에서 반영하면 UI의 DAG 목록과 import 오류를 확인합니다. 폴더 쓰기 권한은 배포 운영자에게 부여합니다.

### 이미지 업데이트

플러그인, Python 패키지 또는 ODBC를 바꿀 때는 DAG를 일시정지하고 실행 중인 작업을 완료한 뒤 [DB를 백업](#1-db와-설정-백업)합니다. `k8s.env`의 `AIRFLOW_IMAGE_TAG`를 새 고유 태그로 바꿉니다.

**1. 빌드:** 빌드 host `khinfow01`의 저장소 루트에서 배포할 커밋으로 갱신한 뒤 실행합니다. containerd worker·namespace·소켓 설정은 [이미지 준비](02-artifacts.md#2-dag-포함-이미지-준비)와 일치시킵니다.

```bash
sudo python3 deploy/airflow/scripts/manage.py build-image --builder nerdctl --build-env deploy/airflow/env/build.env
```

Docker 빌드 호스트는 `--builder docker`를 사용합니다. 다른 env를 쓴다면 빌드와 Makefile 명령에 같은 파일을 지정합니다.

**2. 전달:** [이미지 전달](02-artifacts.md#이미지-전달)로 Worker가 새 이미지를 사용할 수 있게 합니다.

### 검사와 배포

배포 실행 호스트에서 실행합니다. 이미지를 변경할 때는 새 태그를 워커에서 사용할 수 있게 한 뒤 진행합니다.

```bash
make airflow-check KUBE_CONTEXT=kubernetes-admin@kubernetes
make airflow-up KUBE_CONTEXT=kubernetes-admin@kubernetes
kubectl --context kubernetes-admin@kubernetes -n airflow get pods -o wide
```

**기대 결과:** Pod가 Ready이고 UI에서 DAG 로딩 오류·Portal 연동·기존 Connection을 확인할 수 있습니다. 필요한 DAG를 직접 활성화합니다. 공유 폴더의 DAG는 재배포 후에도 같은 볼륨에서 읽습니다.

배포 도구는 Helm의 `--wait`·`--atomic`을 사용하지 않습니다. 공식 chart의 post-install migration hook과 Pod의 migration 대기가 서로 기다리는 상황을 피하고, hook이 끝난 뒤 rollout을 따로 확인합니다.
실패해도 리소스를 자동 삭제하거나 DB를 되돌리지 않습니다. Helm rollback은 DB schema를 복구하지 않으므로 DB는 해당 버전의 백업으로 복원합니다.

### Airflow 2.x DB 업그레이드

이 구성은 Airflow 3.3.2와 API v2를 사용합니다. 2.x DB를 올릴 때는 다음을 지킵니다.

1. 지원되는 2.7 이상 버전에서 실행 중 작업을 정리하고 기존 scheduler·webserver·triggerer를 중지합니다.
2. DB·Fernet 키·설정을 백업합니다. 3.x migration은 DB schema를 변경하므로 되돌릴 때는 해당 DB 백업과 이전 이미지가 함께 필요합니다.
3. 배포 후 API server·DAG processor 준비, 기존 Connection·Variable 복호화, 시험 DAG 실행을 확인한 뒤 업무 DAG를 활성화합니다.
4. Keycloak client의 callback은 `/auth/oauth-authorized/keycloak`입니다. Portal에서 DAG 현황을 조회한다면 API v2·JWT client가 포함된 Portal API 이미지를 함께 배포하고
   Portal의 `AIRFLOW_BASE_URL`을 [Portal 설정](03-deploy.md#6-접속과-연동-확인)의 값으로 맞춥니다.

## 5. 실패 단계 확인

먼저 읽기 전용 명령으로 상태와 로그를 확인합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow get pods,pvc,jobs
kubectl --context kubernetes-admin@kubernetes -n airflow get events --sort-by=.lastTimestamp
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-api-server --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-dag-processor --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs deployment/airflow-triggerer --tail=100
kubectl --context kubernetes-admin@kubernetes -n airflow logs statefulset/airflow-postgres --tail=100
```

마지막 명령은 내부 DB를 사용할 때만 실행합니다.

| 증상 | 확인할 항목 | 다음 조치 |
| --- | --- | --- |
| chart 준비 필요·SHA 불일치 | 파일 위치·고정 버전 | [chart 준비](02-artifacts.md#1-공식-chart-준비)에 따라 반입하고 `AIRFLOW_CHART_FILE` 확인 |
| 실제 값으로 교체·필수값 오류 | 오류에 표시된 env 키 | [환경설정](01-prepare.md#환경설정)을 보완한 뒤 check 재실행 |
| 기존 비밀값과 불일치·Secret 없음 | 기존 DB 비밀번호·Fernet 키와 사용 중인 env | [Secret 복원](#2-secret-복원). init-secrets 재실행으로 해결하지 않음 |
| OIDC CA ConfigMap 없음 | `AIRFLOW_OIDC_CA_CONFIGMAP`과 namespace | [OIDC CA ConfigMap 준비](03-deploy.md#2-oidc-ca-configmap-준비) |
| Pending·PVC 미연결 | Worker Ready·hostname label·PV nodeAffinity·디스크 경로 | 지정 노드와 경로·권한 확인 |
| ImagePullBackOff | repository:tag·registry 접근·imagePullSecret | [이미지 전달](02-artifacts.md#이미지-전달)로 Worker의 이미지 접근 복구 |
| ODBC mount 실패 | 호스트 디렉터리·Secret 존재 | 실제 DSN·인증서 전체와 읽기 권한 준비 |
| migration·관리자 Job 실패 | 아래 Job 로그 | 원인 해결 후 재배포, DB/PVC 삭제 금지 |
| Pod는 Ready지만 HTTPS 실패 | DNS·Traefik 감시 namespace·TLS·Ingress | port-forward로 앱 접속을 분리 확인 후 라우팅 점검 |
| Portal 호출 실패 | API URL·trigger token·네트워크 | 양쪽 계약과 실제 호출 확인 |

```bash
read -r -p '확인할 Job 이름: ' AIRFLOW_JOB_NAME
kubectl --context kubernetes-admin@kubernetes -n airflow logs "job/$AIRFLOW_JOB_NAME" --all-containers=true --tail=100
```

원인을 고친 뒤 check → up 순서로 재실행합니다. 배포 실패 시 자동 DB rollback은 수행되지 않습니다.

## 6. CPU·메모리 부하 테스트

`scheduler_resource_load_test` DAG의 **Trigger DAG**에서 `target`과 `duration_seconds`를 설정합니다.

| `target` | 부하 대상 | 기본 시간 | 입력 범위 |
| --- | --- | --- | --- |
| `scheduler` (기본) | Airflow 스케줄러 컨테이너 | 120초 | 1~900초 |
| `workers` | `khinfow01`, `khplanew01`의 테스트 Pod | 3,600초 | 10~86,400초 |

워커 모드에서는 각 노드에 Pod를 하나씩 띄워 낮은 우선순위로 PBKDF2 연산을 반복합니다. 메모리는 노드의 `MemAvailable`과 Pod의 cgroup 한도에 따라 조정하며, 4GiB와 전체 메모리의 10% 중 큰 값을 노드 여유로 남깁니다.

### DAG 반영

[공유 폴더 관리](#dag-파일-추가수정삭제)에 따라 `scheduler_resource_load_test.py`를 반영합니다. 이미지 기반 배포에서 한 번만 테스트할 경우 스케줄러와 DAG Processor 양쪽의 `/opt/airflow/dags/`에 임시로 복사할 수 있습니다. Pod가 재생성되면 임시 파일이 사라집니다.

별도 `worker_node_resource_load_test.py`를 이미 추가한 환경은 해당 테스트가 끝난 뒤 운영 DAG 폴더에서 그 파일을 제거합니다.

### 워커 모드 준비와 시작

1. CP1에서 두 노드의 Ready 상태와 `Allocatable`을 확인합니다.

   ```bash
   kubectl --context kubernetes-admin@kubernetes get nodes khinfow01 khplanew01
   kubectl --context kubernetes-admin@kubernetes describe nodes khinfow01 khplanew01
   ```

2. 에어갭 배포라면 스케줄러의 Airflow 이미지 태그를 두 워커 모두의 containerd에 반입합니다. 이미지 pull Secret을 사용하는 환경은 같은 이름의 Secret을 테스트 namespace에도 준비합니다. [이미지 전달](02-artifacts.md#이미지-전달)
3. CP1에서 테스트 전용 namespace와 권한을 적용합니다. 아래 manifest는 `airflow` namespace의 `airflow-scheduler` 서비스 계정을 사용합니다.

   ```bash
   kubectl --context kubernetes-admin@kubernetes apply -f deploy/airflow/k8s/node-load-test.yaml
   ```

4. Airflow UI에서 DAG를 활성화한 다음 **Trigger DAG**의 `target`을 `workers`로 선택합니다. 처음 배치와 지표를 확인할 때는 `duration_seconds`를 60초로 설정할 수 있습니다.

### 확인과 종료

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow-node-load-test get pods -o wide
kubectl --context kubernetes-admin@kubernetes top nodes khinfow01 khplanew01
```

두 Pod가 각각 지정된 노드에서 `Running`이고 Airflow 태스크 로그에 CPU 스레드 수와 메모리 목표가 표시되는지 확인합니다. `kubectl top`은 metrics-server가 구성된 환경에서 사용할 수 있습니다. Pod가 `Pending`이면 테스트 namespace의 events에서 노드 배치와 이미지 pull 오류를 확인합니다.

조기에 중단하려면 DagRun을 실패로 표시합니다. 노드 부하를 즉시 종료해야 할 때는 테스트 라벨의 Pod를 삭제합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n airflow-node-load-test \
  delete pods -l app.kubernetes.io/name=airflow-node-load-test
```

태스크 종료 시 Airflow가 테스트 Pod를 정리하며 Pod에도 실행 기한이 설정됩니다.
