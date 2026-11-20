# Airflow 백업·이전·업데이트와 문제 해결

[Airflow 가이드](../README.md)

설치·업데이트 절차는 [Airflow 가이드](../README.md)에 있습니다. 이 문서는 설치 후의 백업·Secret 복원·DB 이전·DAG 관리·이미지 업데이트 준비·장애 확인·부하 테스트입니다.
명령은 관리 호스트 저장소 루트에서 실행합니다. 다른 서버에서 하는 작업은 절에 실행 위치를 표시하며 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.
DB 명령은 `POSTGRES_MODE=internal`, namespace·DB·사용자 `airflow` 기준입니다. 외부 DB는 해당 DB 운영 절차로 백업·복원하고 내부 StatefulSet 명령을 사용하지 않습니다.

- [1. DB와 설정 백업](#1-db와-설정-백업)
- [2. Secret 복원](#2-secret-복원)
- [3. 기존 Compose DB 이전](#3-기존-compose-db-이전)
- [4. DAG·이미지 업데이트](#4-dag이미지-업데이트)
- [5. 실패 단계 확인](#5-실패-단계-확인)
- [6. CPU·메모리 부하 테스트](#6-cpu메모리-부하-테스트)

[조회] 작업 전 Pod 상태를 확인합니다.

```bash
kubectl --context "<context>" -n airflow get pods
```

## 1. DB와 설정 백업

DB와 **`k8s.env` 전체를 같은 시점의 백업으로 보관**합니다. env에는 Fernet 키와 DB 비밀번호가 있으며,
Fernet 키를 잃으면 기존 Connection·Variable의 암호화된 값을 읽을 수 없습니다.

PostgreSQL은 Airflow Helm release와 별도로 관리하므로 `helm uninstall airflow`가 DB를 삭제하지 않습니다.
PV 정책은 Retain이며 namespace나 PVC를 삭제해도 자동으로 다시 연결되지 않습니다. 정상 업데이트에서는 이 리소스를 삭제하지 않습니다.

정해진 백업 주기와 [이미지 업데이트](#이미지-업데이트)·DB 이전 전에 실행합니다. 실행 시각별 custom-format dump를 만들고 실패한 백업은 완료 파일로 남기지 않으며, 비밀번호는 컨테이너의 기존 Secret 환경에서 읽습니다.

[변경] 클러스터는 바꾸지 않고 관리 호스트의 `$HOME/airflow-backups`에 dump 파일을 만듭니다. 저장소의 `deploy/airflow` 아래에는 만들지 않습니다. 추적되지 않는 파일이 생기면 배포 상태 대조가 `앱 경로의 미커밋 변경` 경고를 냅니다.

```bash
(
  set -eu
  umask 077
  backup_dir="$HOME/airflow-backups"
  mkdir -p "$backup_dir"
  backup_file="$backup_dir/airflow-$(date +%Y%m%d-%H%M%S).dump"
  kubectl --context "<context>" -n airflow exec airflow-postgres-0 -- \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h 127.0.0.1 -U airflow -d airflow -Fc' \
    > "$backup_file.partial"
  mv "$backup_file.partial" "$backup_file"
  ls -l "$backup_file"
)
```

성공: 마지막 줄에 `airflow-<시각>.dump` 파일의 크기와 경로가 출력됩니다. 실패하면 `.partial` 파일만 남으며 완료된 백업이 아닙니다. 사본은 다른 저장매체에 보관합니다. 같은 서버·디스크에만 두면 디스크 장애를 복구할 수 없습니다.

## 2. Secret 복원

사전 검사가 다음 이유로 중단된 경우에 사용합니다.

- 기존 DB PVC, `airflow-metadata` Secret 또는 scheduler·API server·DAG processor·triggerer Deployment가 남아 있는데 `airflow-fernet`이 없음
- 기존 `airflow-postgres` PVC가 있는데 `airflow-postgres` Secret이 없음

복원에는 DB를 만들 때의 원래 Fernet 키와 실제 DB 비밀번호가 필요하며, 그 값이 env의 `AIRFLOW_FERNET_KEY`·`POSTGRES_PASSWORD`에 들어 있어야 합니다. 새 키를 생성하지 않으며 `init-secrets`를 다시 실행해 해결하지 않습니다.
외부 DB만 남고 클러스터의 설치 흔적이 모두 사라진 환경은 자동으로 판별할 수 없으므로 DB 백업과 함께 보관한 원래 Fernet 키·env를 먼저 복원합니다.
원래 값이 든 env가 없으면 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일) 절로 준비하고, 원래 값인지 확인할 수 없으면 멈추고 보고합니다. 다른 값으로 Secret을 만들지 않습니다.

[승인] env의 두 값이 원래 값이라는 확인을 받은 뒤 실행합니다. 다른 값으로 만들면 DB 접속과 저장된 Connection 복호화가 실패합니다. 없는 Secret만 만들고 이미 있는 Secret은 바꾸지 않습니다. 저장소 밖 env를 쓰면 `AIRFLOW_ENV=<경로>`를 붙입니다.

```bash
make airflow-secret-restore KUBE_CONTEXT="<context>"
```

성공: `Secret 복원: airflow-postgres, airflow-fernet`처럼 만든 Secret 이름이 나옵니다. `없음(두 Secret이 이미 있습니다)`이면 Secret은 있는데 env와 값이 다른 경우이므로 env 값을 기존 값과 대조합니다.

[검사] 이어서 env와 Secret의 일치를 확인합니다.

```bash
make airflow-check KUBE_CONTEXT="<context>"
```

성공: `설정·차트·기존 리소스·TLS·배치 검사 통과`.

## 3. 기존 Compose DB 이전

이 절은 DB 이전이 별도로 결정된 환경에만 적용하며 신규 설치에는 사용하지 않습니다.
[승인] 데이터 이전입니다. 대상 DB·순서·영향을 보여 주고 승인받은 뒤 진행합니다. 1·2번은 기존 Compose 서버에서 실행하며 접속은 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)와 같은 방법을 씁니다.

1. 기존 DAG를 일시정지하고 실행 중인 작업을 종료·완료시킨 후 기존 scheduler/webserver를 중지합니다.
2. 기존 PostgreSQL 16에서 `pg_dump -Fc`로 백업하고 기존 Fernet 키·Connection·Variable을 확인합니다.
3. 새 서버 env에 기존 Fernet 키를 입력하고 새 이미지·chart·디스크를 준비한 뒤 [render](03-deploy.md#배포-내용-미리-보기)·[check](03-deploy.md#검사-범위)를 실행합니다.
4. 전용 namespace와 `airflow-postgres` Secret(`password` 키)을 [Secret 복원](#2-secret-복원)의 명령으로 먼저 만들고, 렌더된 `storage.json`, `postgres.json`만 적용합니다. 값은 `k8s.env`의 DB 비밀번호와 일치시킵니다.
5. 새 DB가 준비되면 **비어 있는 새 airflow DB에만** `pg_restore --no-owner --no-acl -U airflow -d airflow`로 복원합니다.
   기존 업무 DB를 덮어쓰지 않습니다. 필요하면 기존 로그도 새 로그 경로에 복사하고 50000:0 권한을 맞춥니다.
6. [가이드](../README.md#a-최초-설치)의 배포를 실행해 공식 chart migration을 적용합니다. 기존 계정은 그대로 사용하며 비밀번호를 자동 초기화하지 않습니다.
7. Portal 연결·기존 Connection 복호화·DAG 상태를 확인하고 하나의 scheduler만 작업을 실행하도록 활성화합니다.

## 4. DAG·이미지 업데이트

### 공유 폴더 전환

Airflow는 워커의 `DAGS_HOST_PATH`를 `airflow-dags` PVC로 공유해 `/opt/airflow/dags`에서 읽습니다. 스케줄러와 DAG Processor는 준비 표식(`.airflow-dags-initialized`)이 있는 볼륨에서 시작합니다.

**최초 설치(실행 중인 Airflow 없음):** `airflow-up`이 `NODE_NAME` 워커(`khinfow01`)의 폴더를 만들고, 폴더가 비어 있으면 이미지의 `/opt/airflow/dags`와 준비 표식을 복사합니다. 이미지의 `/opt/airflow/dags`는 빌드한 commit의 `apps/airflow/dags`를 그대로 복사한 것입니다. 폴더에 파일이나 준비 표식이 이미 있으면 바꾸지 않습니다.

**기존 설치에서 전환:** `airflow-scheduler`가 이미 배포된 환경에는 `airflow-up`이 DAG를 복사하지 않으므로 아래 순서로 준비합니다. 2·3번은 `NODE_NAME` 워커(`khinfow01`)에서 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 방법으로 실행합니다. 공유 폴더를 처음 연결하기 전에 기존 DAG를 [일시정지](#dag-목록-확인과-활성화)하고 실행 중인 작업을 완료한 뒤 [DB를 백업](#1-db와-설정-백업)합니다.

1. [변경] 관리 호스트에서 현재 DAG Processor의 파일을 백업합니다. 클러스터는 바꾸지 않고 백업 파일을 만듭니다. 마지막 줄에 나온 파일 경로를 보고에 남깁니다.

   ```bash
   (
     set -eu
     umask 077
     backup_dir="$HOME/airflow-backups"
     mkdir -p "$backup_dir"
     archive="$backup_dir/dags-$(date +%Y%m%d-%H%M%S).tar"
     kubectl --context "<context>" -n airflow \
       exec deployment/airflow-dag-processor -c dag-processor -- \
       tar --exclude=__pycache__ -C /opt/airflow/dags -cf - . > "$archive.partial"
     tar -tf "$archive.partial" >/dev/null
     mv "$archive.partial" "$archive"
     printf '%s\n' "$archive"
   )
   ```

2. [변경] 1번에서 만든 tar를 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 파일 전송 형식으로 `khinfow01`에 복사합니다. 이어서 `khinfow01`에서 tar의 실제 경로를 넣어 아래를 실행합니다. 대상 디렉터리에 파일이 이미 있으면 우선 보존합니다. 전환과 함께 업데이트할 DAG 파일은 **준비 표식을 만들기 전에** [DAG 파일 추가·수정·삭제](#dag-파일-추가수정삭제)의 방법으로 필요한 버전을 복사합니다.

   ```bash
   sudo -n install -d -o root -g root -m 0755 /appdata/airflow/dags
   sudo -n tar --extract --skip-old-files --no-same-owner --no-same-permissions \
     --file <DAG 백업 tar 절대 경로> --directory /appdata/airflow/dags
   ls -la /appdata/airflow/dags
   ```

   성공: 목록에 기존 DAG 파일과 공통 Python 파일이 보입니다.

3. [변경] DAG와 공통 Python 파일이 옮겨졌고 Airflow(UID 50000)가 읽을 수 있는 권한인지 2번의 목록으로 확인한 뒤 `khinfow01`에서 준비 표식을 만듭니다.

   ```bash
   sudo -n install -o root -g root -m 0644 /dev/null /appdata/airflow/dags/.airflow-dags-initialized
   ls -l /appdata/airflow/dags/.airflow-dags-initialized
   ```

   이어서 env의 `DAGS_HOST_PATH`를 실제 경로로 두고 관리 호스트에서 [가이드 B](../README.md#b-업데이트)의 순서로 배포합니다. `DAGS_HOST_PATH`를 처음 지정하면 이미지 tag 계산에서 `dags`가 빠져 tag가 바뀌므로, `make airflow-check`의 `이미지 변경:` 줄이 `있음`이면 가이드 B의 [승인] 행을 따릅니다.

4. [조회] `airflow-dags` PVC가 `Bound`이고 스케줄러·DAG Processor가 `Ready`인지 확인합니다.

   ```bash
   kubectl --context "<context>" -n airflow get pvc,pods
   ```

   이어서 [DAG 목록 확인과 활성화](#dag-목록-확인과-활성화)의 명령으로 기존 업무 DAG 목록과 import 오류를 확인한 뒤 테스트할 DAG를 활성화합니다. 문제가 있으면 `DAGS_HOST_PATH`를 비우고 이전 이미지 태그로 검사·배포해 이미지 기반으로 복구합니다. 공유 경로의 파일과 PV/PVC는 복구용으로 보관합니다.

### DAG 파일 추가·수정·삭제

워커(`khinfow01`)의 `DAGS_HOST_PATH`(현재 `/appdata/airflow/dags`)에서 파일을 관리합니다. 폴더 소유자는 `root:root`·`0755`이므로 쓰기는 sudo로 합니다. 재배포는 필요 없으며 Airflow가 다음 스캔에서 반영합니다. 아래 명령은 `khinfow01`에서 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

1. [변경] 추가·수정. 관리 호스트 checkout의 `apps/airflow/dags/<파일>.py`를 노드 SSH의 파일 전송 형식으로 `khinfow01`의 `/tmp/<파일>.py`에 복사합니다. 이어서 같은 디렉터리의 `.tmp` 파일에 복사한 뒤 최종 `.py` 이름으로 이동합니다. Airflow가 쓰는 도중의 파일을 읽지 않게 하는 순서입니다.

   ```bash
   sudo -n install -o root -g root -m 0644 /tmp/<파일>.py /appdata/airflow/dags/<파일>.py.tmp
   sudo -n mv /appdata/airflow/dags/<파일>.py.tmp /appdata/airflow/dags/<파일>.py
   ls -l /appdata/airflow/dags/<파일>.py
   ```

2. [변경] 삭제·교체. 먼저 그 DAG를 [일시정지](#dag-목록-확인과-활성화)하고 실행 중인 작업이 끝난 뒤 합니다. 실행 중인 작업은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 Airflow 화면의 DAG Run 상태에서 확인합니다. 교체는 1번과 같고 삭제는 아래 명령입니다.

   ```bash
   sudo -n rm /appdata/airflow/dags/<파일>.py
   ls -l /appdata/airflow/dags
   ```

3. [조회] 반영된 뒤 [DAG 목록 확인과 활성화](#dag-목록-확인과-활성화)의 명령으로 DAG 목록과 import 오류를 확인합니다.

### DAG 목록 확인과 활성화

DAG 목록·import 오류 조회, 일시정지·활성화는 scheduler Pod의 Airflow CLI로 합니다. `<DAG ID>`는 목록의 `dag_id` 값입니다. 화면에서 확인할 때는 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절을 따릅니다.

[조회] DAG 목록과 import 오류입니다.

```bash
kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags list
kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags list-import-errors
```

성공: 기대한 DAG가 목록에 있고 import 오류가 없습니다. 목록의 `is_paused`가 일시정지 여부입니다.

[변경] DAG 하나를 일시정지합니다. 배포·DAG 교체 전에 실행 중인 작업을 더 만들지 않게 할 때 씁니다.

```bash
kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags pause <DAG ID>
```

[변경] DAG 하나를 활성화합니다. 업무 DAG는 요청에 포함된 것만, 기존 scheduler의 중복 실행이 없는지 확인한 뒤 활성화합니다.

```bash
kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags unpause <DAG ID>
```

성공: 위 [조회]의 `airflow dags list` 출력에서 그 DAG의 `is_paused`가 바뀌어 있습니다.

### 이미지 업데이트

플러그인, Python 패키지 또는 ODBC를 바꿀 때의 배포 명령은 [가이드 B](../README.md#b-업데이트)에 있습니다. `make ops-deploy`에서 검사 다음 단계인 `airflow-image`가 빌드와 사내 이미지 저장소 push를 수행하고, 같은 태그가 이미 있으면 빌드하지 않습니다.

- 배포 전에 DAG를 [일시정지](#dag-목록-확인과-활성화)하고 실행 중인 작업을 완료한 뒤 [DB를 백업](#1-db와-설정-백업)합니다.
- `AIRFLOW_IMAGE_TAG=3.3.2-auto`이면 소스 변경에 따라 태그가 자동으로 바뀌므로 env를 고치지 않습니다. 태그를 직접 쓰는 환경만 새 고유 태그로 바꿉니다.
- 관리 호스트의 저장소 루트를 배포할 커밋으로 갱신한 뒤 실행합니다. containerd worker·namespace·소켓 설정은 [이미지 준비](02-artifacts.md#2-dag-포함-이미지-준비)와 일치시킵니다.
- Docker 빌드 호스트는 `--builder docker`를 사용합니다. 다른 env를 쓴다면 빌드와 Makefile 명령에 같은 파일을 지정합니다.
- registry를 쓰지 않는 환경만 [이미지 전달](02-artifacts.md#이미지-전달)로 Worker에 반입합니다.
- 배포 후 [DAG 목록 확인과 활성화](#dag-목록-확인과-활성화)의 명령으로 DAG 로딩 오류를 확인하고 일시정지했던 DAG를 다시 활성화합니다. Portal 연동·기존 Connection은 [접속과 연동 확인](03-deploy.md#접속과-연동-확인)의 항목으로 확인합니다. 공유 폴더의 DAG는 재배포 후에도 같은 볼륨에서 읽습니다.

배포 도구는 Helm의 `--wait`·`--atomic`을 사용하지 않습니다. 공식 chart의 post-install migration hook과 Pod의 migration 대기가 서로 기다리는 상황을 피하고, hook이 끝난 뒤 rollout을 따로 확인합니다.
실패해도 리소스를 자동 삭제하거나 DB를 되돌리지 않습니다. Helm rollback은 DB schema를 복구하지 않으므로 DB는 해당 버전의 백업으로 복원합니다.

### Airflow 2.x DB 업그레이드

이 구성은 Airflow 3.3.2와 API v2를 사용합니다. 2.x DB를 올릴 때는 다음을 지킵니다.

1. 지원되는 2.7 이상 버전에서 실행 중 작업을 정리하고 기존 scheduler·webserver·triggerer를 중지합니다.
2. DB·Fernet 키·설정을 백업합니다. 3.x migration은 DB schema를 변경하므로 되돌릴 때는 해당 DB 백업과 이전 이미지가 함께 필요합니다.
3. 배포 후 API server·DAG processor 준비, 기존 Connection·Variable 복호화, 시험 DAG 실행을 확인한 뒤 업무 DAG를 활성화합니다.
4. Keycloak client의 callback은 `/auth/oauth-authorized/keycloak`입니다. Portal에서 DAG 현황을 조회한다면 API v2·JWT client가 포함된 Portal API 이미지를 함께 배포하고
   Portal의 `AIRFLOW_BASE_URL`을 [Portal 설정](03-deploy.md#접속과-연동-확인)의 값으로 맞춥니다.

## 5. 실패 단계 확인

[조회] 먼저 읽기 전용 명령으로 상태와 로그를 확인합니다.

```bash
kubectl --context "<context>" -n airflow get pods,pvc,jobs
kubectl --context "<context>" -n airflow get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-api-server --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-dag-processor --tail=100
kubectl --context "<context>" -n airflow logs deployment/airflow-triggerer --tail=100
kubectl --context "<context>" -n airflow logs statefulset/airflow-postgres --tail=100
```

마지막 명령은 내부 DB를 사용할 때만 실행합니다.

| 증상 | 확인할 항목 | 다음 조치 |
| --- | --- | --- |
| chart 준비 필요·SHA 불일치 | 파일 위치·고정 버전 | [chart 준비](02-artifacts.md#1-공식-chart-준비)에 따라 다시 받거나 반입하고 `AIRFLOW_CHART_FILE` 확인 |
| 실제 값으로 교체·필수값 오류 | 오류에 표시된 env 키 | [환경설정](01-prepare.md#환경설정)의 뜻에 맞는 값을 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 env에 채운 뒤 check 재실행 |
| 기존 비밀값과 불일치·Secret 없음 | 기존 DB 비밀번호·Fernet 키와 사용 중인 env | [Secret 복원](#2-secret-복원). init-secrets 재실행으로 해결하지 않음 |
| OIDC CA ConfigMap과 CA 묶음 파일이 모두 없음 | `AIRFLOW_OIDC_CA_CONFIGMAP`, `AIRFLOW_OIDC_CA_FILE` | [사내 CA 묶음](../../README.md#사내-ca-묶음)을 만들거나 CA 파일 경로 지정. [OIDC CA ConfigMap](03-deploy.md#oidc-ca-configmap) |
| Pending·PVC 미연결 | Worker Ready·hostname label·PV nodeAffinity·디스크 경로 | [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)로 지정 노드의 [폴더·권한](01-prepare.md#worker-폴더-직접-준비)을 조회. PV·PVC를 지우거나 다시 만들지 않음 |
| ImagePullBackOff | repository:tag·registry 접근·노드의 저장소 인증서 신뢰·imagePullSecret | 노드의 [CA 신뢰](../../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰) 확인. registry를 쓰지 않으면 [이미지 전달](02-artifacts.md#이미지-전달)로 Worker의 이미지 접근 복구 |
| ODBC mount 실패 | 호스트 디렉터리·Secret 존재 | [ODBC 파일 안내](../odbc/README.md#worker에-반영)로 실제 DSN·인증서 전체와 읽기 권한 준비 |
| migration·관리자 Job 실패 | 아래 Job 로그 | 멈추고 Job 로그와 함께 보고. DB/PVC 삭제 금지 |
| Pod는 Ready지만 HTTPS 실패 | DNS·Traefik 감시 namespace·TLS·Ingress | [Service 직접 조회](03-deploy.md#접속과-연동-확인)로 앱 응답을 분리 확인한 뒤 라우팅 점검. DNS만 없으면 smoke는 `DNS 미등록`으로 통과하며 [DNS](../../shared/docs/infrastructure/access.md#dns) 절로 등록 |
| Portal 호출 실패 | API URL·trigger token·네트워크 | 양쪽 계약과 실제 호출 확인 |

[조회]
```bash
kubectl --context "<context>" -n airflow logs "job/<확인할 Job 이름>" --all-containers=true --tail=100
```

원인을 고친 뒤 [가이드](../README.md#a-최초-설치)의 배포 명령을 다시 실행합니다. 배포는 check를 먼저 통과해야 up으로 넘어갑니다. 배포 실패 시 자동 DB rollback은 수행되지 않습니다.

## 6. CPU·메모리 부하 테스트

`scheduler_resource_load_test` DAG를 실행할 때 `target`과 `duration_seconds`를 지정합니다. Airflow 화면에서는 **Trigger DAG**의 입력란이고, 명령으로는 `airflow dags trigger`의 `--conf`입니다.

| `target` | 부하 대상 | 기본 시간 | 입력 범위 |
| --- | --- | --- | --- |
| `scheduler` (기본) | Airflow 스케줄러 컨테이너 | 120초 | 1~900초 |
| `workers` | `khinfow01`, `khplanew01`의 테스트 Pod | 3,600초 | 10~86,400초 |

워커 모드에서는 각 노드에 Pod를 하나씩 띄워 낮은 우선순위로 PBKDF2 연산을 반복합니다. 메모리는 노드의 `MemAvailable`과 Pod의 cgroup 한도에 따라 조정하며, 4GiB와 전체 메모리의 10% 중 큰 값을 노드 여유로 남깁니다.

### DAG 반영

[공유 폴더 관리](#dag-파일-추가수정삭제)에 따라 `scheduler_resource_load_test.py`를 반영합니다. 이미지 기반 배포에서 한 번만 테스트할 경우 스케줄러와 DAG Processor 양쪽의 `/opt/airflow/dags/`에 임시로 복사할 수 있습니다. Pod가 재생성되면 임시 파일이 사라집니다.

별도 `worker_node_resource_load_test.py`를 이미 추가한 환경은 해당 테스트가 끝난 뒤 운영 DAG 폴더에서 그 파일을 제거합니다.

### 워커 모드 준비와 시작

1. [조회] 관리 호스트에서 두 노드의 Ready 상태와 `Allocatable`을 확인합니다.

   ```bash
   kubectl --context "<context>" get nodes khinfow01 khplanew01
   kubectl --context "<context>" describe nodes khinfow01 khplanew01
   ```

2. [변경] 사내 이미지 저장소를 쓰지 않는 에어갭 배포라면 스케줄러의 Airflow 이미지 태그를 두 워커 모두의 containerd에 반입합니다. 방법은 [이미지 전달](02-artifacts.md#registry-없이-전달하는-경우)이며 각 워커에서 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)의 방법으로 실행합니다. 이미지 pull Secret을 사용하는 환경은 같은 이름의 Secret을 테스트 namespace에도 준비합니다.
3. [변경] 관리 호스트에서 테스트 전용 namespace와 권한을 적용합니다. 아래 manifest는 `airflow` namespace의 `airflow-scheduler` 서비스 계정을 사용합니다.

   ```bash
   kubectl --context "<context>" apply -f deploy/airflow/k8s/node-load-test.yaml
   kubectl --context "<context>" get namespace airflow-node-load-test
   ```

   성공: namespace `airflow-node-load-test`가 `Active`입니다.

4. [변경] 테스트 DAG를 활성화하고 `target`을 `workers`로 지정해 실행합니다. 처음 배치와 지표를 확인할 때는 `duration_seconds`를 60초로 둡니다.

   ```bash
   kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- airflow dags unpause scheduler_resource_load_test
   kubectl --context "<context>" -n airflow exec deployment/airflow-scheduler -- \
     airflow dags trigger scheduler_resource_load_test --conf '{"target": "workers", "duration_seconds": 60}'
   ```

   성공: 아래 [확인과 종료](#확인과-종료)의 조회에서 두 노드에 테스트 Pod가 `Running`으로 보입니다.

### 확인과 종료

[조회]
```bash
kubectl --context "<context>" -n airflow-node-load-test get pods -o wide
kubectl --context "<context>" top nodes khinfow01 khplanew01
```

두 Pod가 각각 지정된 노드에서 `Running`이고 Airflow 태스크 로그에 CPU 스레드 수와 메모리 목표가 표시되는지 확인합니다. `kubectl top`은 metrics-server가 구성된 환경에서 사용할 수 있습니다. Pod가 `Pending`이면 테스트 namespace의 events에서 노드 배치와 이미지 pull 오류를 확인합니다.

조기에 중단하려면 Airflow 화면에서 DagRun을 실패로 표시합니다([화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인)).

[변경] 노드 부하를 즉시 종료해야 할 때만 테스트 라벨의 Pod를 삭제합니다. 대상은 테스트 namespace의 Pod뿐입니다. 삭제 뒤 위 [조회] 명령으로 Pod가 없어졌는지 확인합니다.

```bash
kubectl --context "<context>" -n airflow-node-load-test \
  delete pods -l app.kubernetes.io/name=airflow-node-load-test
```

태스크 종료 시 Airflow가 테스트 Pod를 정리하며 Pod에도 실행 기한이 설정됩니다.
