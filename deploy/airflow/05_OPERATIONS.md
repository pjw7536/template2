# 05. Airflow 백업·이전·업데이트와 문제 해결

[시작 안내](README.md) · 이전: [단계별 실행](04_SETUP_FLOW.md)

명령은 저장소 루트에서 실행합니다. 새 터미널에서는 context를 다시 입력합니다.
현재 최초 설치는 새 DB로 시작하므로 **2절의 Compose DB 이전은 생략**합니다.
최초 설치는 [01 서버 준비](01_SERVER_SETUP.md)부터 진행하고, 설치 후에는 이 문서의 백업·업데이트 절차를 사용합니다.
아래 DB 백업과 이전 예시는 `POSTGRES_MODE=internal`, namespace·DB·사용자 `airflow` 기준입니다.
외부 DB는 해당 DB 운영 절차로 백업·복원하고 내부 StatefulSet 명령을 사용하지 않습니다.

```bash
read -r -p '운영 Kubernetes context: ' AIRFLOW_KUBE_CONTEXT
kubectl --context "$AIRFLOW_KUBE_CONTEXT" -n airflow get pods
```

## Fernet Secret 복원과 배포 사전 검사

기존 DB PVC, metadata Secret 또는 scheduler·webserver·triggerer Deployment가 남아 있는데
`airflow-fernet`이 없으면 배포를 중단합니다.

복원할 때는 DB 백업 시점의 원래 Fernet 키를 사용합니다. 새 키를 생성하지 않습니다.
이 키를 `airflow-fernet`의 `fernet-key`로 복원하고, 같은 값이 들어 있는 env로 다시 검사합니다.
복원 입력은 접근 권한을 제한한 파일로 전달해 비밀값이 명령행·로그에 노출되지 않게 합니다.
이미 Secret이 있으면 그 값과 env의 키가 일치해야 합니다.

외부 DB만 남고 클러스터의 모든 설치 흔적이 사라진 환경은 자동으로 기존 DB인지 판별할 수 없습니다.
이 경우에도 DB 백업과 함께 보관한 원래 Fernet 키·env를 복원해야 하며 새 키로 초기화하지 않습니다.

기본 설정은 control-plane/master `NoSchedule` taint를 허용합니다. 실제 검사는 Helm override까지
반영한 각 Deployment·Job의 최종 toleration과 nodeSelector를 사용합니다. 외부 DB 모드에서는
별도 toleration으로 전용 노드를 허용할 수 있습니다. 내부 PostgreSQL은 자체 원본의 toleration을
따로 검사하므로 Airflow만 허용해도 DB를 배치할 수 없으면 중단합니다.
필수 image pull·ODBC Secret, OIDC CA ConfigMap과 IngressClass는 `airflow-check`에서도 확인하고,
누락되면 공용 Traefik·권한을 변경하기 전에 중단합니다. TLS 원본 입력은 공용 저장소에만 등록하며 앱 namespace에는 복제하지 않습니다.
TLS 입력은 인증서의 도메인·만료와 개인키 일치를 모두 검사합니다.

## 1. DB와 설정 백업

DB와 **`k8s.env` 전체를 같은 시점의 백업으로 보관**합니다.
이 env에는 Fernet 키와 DB 비밀번호가 들어 있습니다.
Fernet 키를 잃으면 기존 Connection·Variable의 암호화된 값을 읽을 수 없습니다.

PostgreSQL은 Airflow Helm release와 별도로 관리합니다.
따라서 `helm uninstall airflow`가 DB를 삭제하지는 않습니다.
PV의 정책은 Retain이며 namespace나 PVC를 삭제해도 자동으로 다시 연결되지 않습니다.
정상 업데이트에서는 이 리소스를 삭제하지 않습니다.

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

이 절은 별도로 DB 이전이 결정된 환경을 위한 참고입니다. 현재 신규 설치에는 적용하지 않습니다.

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

업데이트는 DAG 일시정지 → 실행 중 작업 완료 → DB 백업 → 새 이미지 태그 지정 순서로 준비합니다.
배포 후 검증을 마친 다음 필요한 DAG를 다시 활성화합니다.

배포 스크립트는 Helm의 `--wait`·`--atomic`을 사용하지 않습니다.
공식 chart의 post-install migration hook과 Pod의 migration 대기가 서로 기다리는 상황을 피하기 위해서입니다.
대신 hook이 끝난 뒤 rollout을 따로 확인합니다.

실패해도 리소스를 자동 삭제하거나 DB를 되돌리지 않습니다.
Helm rollback은 DB schema까지 복구하지 않으므로 DB는 해당 버전의 복원 절차를 따릅니다.
이 구성은 Airflow 2.11.0 전환용입니다. Airflow 3으로 올릴 때는 DAG·API·인증 호환성을 별도로 검증합니다.

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
