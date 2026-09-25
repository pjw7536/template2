# 05. Airflow 백업·이전·업데이트와 문제 해결

[시작 안내](README.md) · 이전: [단계별 실행](04_SETUP_FLOW.md)

명령은 저장소 루트에서 실행합니다. 새 터미널에서는 context를 다시 입력합니다.
아래 DB 백업과 이전 예시는 `POSTGRES_MODE=internal`, namespace·DB·사용자 `airflow` 기준입니다.
외부 DB는 해당 DB 운영 절차로 백업·복원하고 내부 StatefulSet 명령을 사용하지 않습니다.

```bash
read -r -p '운영 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods
```

## 1. DB와 설정 백업

PostgreSQL은 Airflow Helm release 밖에서 관리하므로 `helm uninstall airflow`가 DB를 삭제하지 않습니다.
PV는 Retain이며 namespace나 PVC 삭제 후 자동 재연결되지 않습니다. 정상 업데이트에서는 삭제하지 마세요.
Fernet 키를 잃으면 기존 Connection·Variable의 암호화된 값을 복호화하지 못합니다.
설정과 Fernet 키가 함께 저장된 **`k8s.env` 전체를 백업**합니다.
Fernet 키·DB 비밀번호는 통합 env에 포함됩니다. DB 백업 시점과 일치하는 env 버전을 함께 보존합니다.

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

## 2. 기존 Compose DB 이전

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

## 3. DAG·이미지 업데이트

업데이트 전 DAG를 일시정지하고 실행 중인 작업이 끝난 뒤 DB를 백업하고 새 이미지 태그를 지정합니다.
업데이트 완료 후 필요한 DAG를 다시 활성화합니다. 공식 chart의 post-install migration hook과
Pod의 migration 대기가 교착하지 않도록 배포 스크립트는 Helm `--wait`·`--atomic`을 사용하지 않고
hook 완료 후 별도로 rollout을 확인합니다. 실패 시 자동 삭제·DB rollback은 수행하지 않습니다.
Helm rollback으로 DB schema까지 되돌아가지는 않으므로 DB 복원은 해당 버전의 절차로 수행합니다.
이번 구성은 기존 2.11.0 배포 전환용이며 Airflow 3 업그레이드는 DAG·API·인증 호환성 검증을 별도로 진행합니다.

DAG를 일시정지하고 실행 중 작업 완료·백업을 확인한 뒤 다음 순서로 진행합니다.
`k8s.env`의 `AIRFLOW_IMAGE_TAG`를 새 고유 태그로 바꾸고, 소스가 있는 빌드 호스트에서 실행합니다.

```bash
python3 deploy/airflow/scripts/manage.py build-image --build-env deploy/airflow/env/build.env
```

[이미지 전달](03_ARTIFACTS.md#2-dag-포함-이미지-준비)을 끝낸 뒤 배포 실행 호스트에서 수행합니다.
다른 env 파일을 쓴다면 빌드와 Makefile 명령에도 같은 파일을 지정합니다.

```bash
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods -o wide
```

완료 기준: 새 이미지의 Pod가 Ready이고 UI에서 DAG 로딩 오류·Portal 연동·기존 Connection을 확인해야 합니다.
기존 DAG의 일시정지 상태는 유지되므로 확인 후 필요한 DAG를 직접 활성화합니다.

## 4. 실패 단계 확인

먼저 읽기 전용 명령으로 상태와 로그를 확인합니다.

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods,pvc,jobs
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get events --sort-by=.lastTimestamp
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow logs deployment/airflow-scheduler --tail=100
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow logs deployment/airflow-webserver --tail=100
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow logs deployment/airflow-triggerer --tail=100
```

내부 DB를 사용하면 추가로 확인합니다.

```bash
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow logs statefulset/airflow-postgres --tail=100
```

| 증상 | 확인할 항목 | 다음 조치 |
| --- | --- | --- |
| chart 준비 필요·SHA 불일치 | 파일 위치·고정 버전 | 03 안내대로 chart 반입, AIRFLOW_CHART_FILE 확인 |
| 실제 값으로 교체·필수값 오류 | 오류에 표시된 env 키 | 02 안내대로 보완 후 check 재실행 |
| 기존 비밀값과 불일치 | 기존 DB 비밀번호·Fernet 키와 사용 중인 env | 실제 운영값 복원, init-secrets 재실행으로 해결하지 않음 |
| Pending·PVC 미연결 | Worker Ready·hostname label·PV nodeAffinity·디스크 경로 | 지정 노드와 경로·권한 확인 |
| ImagePullBackOff | repository:tag·registry 접근·imagePullSecret | Worker의 이미지 접근 복구 |
| ODBC mount 실패 | 호스트 디렉터리·Secret 존재 | 실제 DSN·인증서 전체와 읽기 권한 준비 |
| migration·관리자 Job 실패 | get jobs 출력의 실패 Job 로그 | 해당 Job 원인 해결 후 재배포, DB/PVC 삭제 금지 |
| Pod는 Ready지만 HTTPS 실패 | DNS·Traefik 감시 namespace·TLS·Ingress | port-forward로 앱 접속을 분리 확인 후 라우팅 점검 |
| Portal 호출 실패 | API URL·trigger token·네트워크 | 양쪽 계약과 실제 호출 확인 |

Job 상세 로그는 `get jobs`에서 확인한 이름으로 조회합니다.

```bash
read -r -p '확인할 Job 이름: ' AIRFLOW_JOB_NAME
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow logs "job/$AIRFLOW_JOB_NAME" --all-containers=true --tail=100
```

실패 원인을 고친 뒤 check → up 순서로 재실행합니다. 배포 실패 시 자동 DB rollback은 수행되지 않습니다.
