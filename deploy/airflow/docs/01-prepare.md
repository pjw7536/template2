# Airflow 서버 준비와 환경설정

[앱 안내](../README.md) · 다음: [chart·이미지·ODBC 준비](02-artifacts.md)

- [서버 준비](#서버-준비)
- [환경설정](#환경설정)

## 서버 준비

**목적:** Airflow를 처음 배포하거나 실행 Worker를 바꿀 때 클러스터·Worker·디스크를 준비합니다. 실제 설치는 [배포와 검증](03-deploy.md#배포와-검증)에서 진행합니다.
**준비물:** Python 3.10 이상, Helm 3.19.0 이상, kubectl, 클러스터 관리자 kubeconfig. 이미지를 직접 빌드하는 호스트는 [이미지 빌드](02-artifacts.md#2-dag-포함-이미지-준비)의 빌더도 필요합니다.

### 1. 실행 위치와 도구 확인

**실행 위치:** CP1의 저장소 루트. 이미지 빌드는 `apps/airflow` 소스를 사용합니다.

가이드의 서버 context는 `kubernetes-admin@kubernetes`입니다. 다른 context를 쓰면 모든 명령의 이름을 해당 값으로 바꿉니다.

```bash
python3 --version
helm version --short
kubectl config get-contexts
kubectl --context kubernetes-admin@kubernetes version
kubectl --context kubernetes-admin@kubernetes get nodes -L kubernetes.io/hostname
```

**기대 결과:** 도구가 최소 버전을 충족하고 선택한 context의 노드가 조회됩니다. chart가 요구하는 Kubernetes 최소 버전은 1.30.13입니다.
현재 클러스터 구성과 다른 앱의 배치는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 확인합니다.
빈 서버를 새 Worker로 추가하려면 [Worker 추가](../../shared/docs/kubernetes/worker.md)를 먼저 진행합니다.
이 도구는 Kubernetes나 Ingress controller를 설치하지 않습니다.

### 2. 실행 Worker 선택

`NODE_NAME`에는 위 출력의 `kubernetes.io/hostname` 값을 그대로 사용합니다. 현재 선언은 `khinfow01`입니다.
Airflow Pod·내부 DB·local PV가 이 노드에 묶이므로 자원·디스크·ODBC 접근을 만족하는 Worker를 선택합니다.
단일 Worker 구성이므로 해당 Worker나 디스크에 장애가 나면 Airflow가 중단됩니다.

최초 설치는 새 DB·전용 계정·Fernet 키를 준비합니다. 재배포는 사용 중인 DB 비밀번호·Fernet 키를 유지하며,
데이터 이전이 필요하면 [백업·이전](04-operations.md)을 따릅니다.
기존 Kubernetes 설치가 `/srv/airflow`를 사용한다면 이전 완료 전까지 env의 기존 경로를 유지하고,
`/appdata/airflow`로 바꿀 때는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 따릅니다.

### 3. Worker의 디스크 준비

**실행 위치:** kubectl 실행 호스트가 아니라 **`NODE_NAME`으로 선택한 Worker**.
경로와 UID/GID는 현재 env 선언 기준이며 실제 env와 일치시킵니다. `POSTGRES_MODE=external`이면 PostgreSQL 경로를 제외합니다.

```bash
sudo install -d -o 999 -g 999 -m 0700 /appdata/airflow/postgres
sudo install -d -o 50000 -g 0 -m 0770 /appdata/airflow/logs
df -h /appdata/airflow/postgres /appdata/airflow/logs
sudo stat -c '%U:%G %a %n' /appdata/airflow/postgres /appdata/airflow/logs
```

**기대 결과:** 두 경로가 있고 소유자가 `999:999`(DB), `50000:0`(로그)입니다.

- local PV는 폴더를 자동으로 만들지 않고, 20Gi 선언은 실제 사용량을 제한하지 않습니다. 디스크 여유 공간을 따로 감시합니다.
- 로그는 자동 삭제하지 않습니다. 보관 정책을 정한 뒤 필요하면 `scheduler.logGroomerSidecar`를 설정합니다.
- 기존 Compose PostgreSQL 데이터 폴더를 바로 연결하지 않습니다. [기존 DB 이전](04-operations.md#3-기존-compose-db-이전)을 따릅니다.
- 외부 DB는 미리 생성한 DB·계정으로 Worker에서 접근할 수 있어야 합니다.

**다음 단계:** [환경설정](#환경설정).

## 환경설정

**목적:** 서버 배포 입력을 준비하고 최초 비밀값을 생성합니다.
**실행 위치:** 저장소 루트.

### 1. 입력 파일 확인

| 파일 | 읽는 명령 | 목적 |
| --- | --- | --- |
| `deploy/airflow/env/k8s.env` | init-secrets·check·render·deploy·build-image, airflow-check·airflow-up·airflow-keycloak-client | 서버·이미지 태그·접속 URL·Secret 입력 |
| `deploy/airflow/env/build.env` | build-image의 `--build-env` | 기본 이미지·APT/PIP mirror·ODBC 설치 입력 |
| `deploy/airflow/helm/values.yaml` | check·render·deploy | 공통 자원·Executor·로그 보관 정책 |

두 env 파일은 Git에서 관리합니다. 비밀값은 env에만 넣고 문서나 Helm override에 복사하지 않습니다.
한 줄에 하나씩 따옴표 없는 `KEY=값`으로 적습니다. env는 데이터 파일이므로 `source`하지 않으며 `$VAR`·`$(...)`도 확장되지 않습니다.

### 2. 최초 설치의 키 생성

**새 DB를 사용하는 최초 설치이며 비밀값이 모두 비어 있을 때만** 실행합니다. 기존 배포의 env가 있으면 건너뛰고 기존 값을 유지합니다.

```bash
python3 deploy/airflow/scripts/manage.py init-secrets \
  --env deploy/airflow/env/k8s.env
chmod 600 deploy/airflow/env/k8s.env
```

**기대 결과:** DB 비밀번호·관리자 비밀번호·Fernet 키·웹서버 키가 생성되고 파일 권한이 0600이 됩니다.
기존 비밀값이 하나라도 있으면 재생성을 거부하며 일반 설정은 보존합니다.
`AIRFLOW_TRIGGER_TOKEN`과 `AIRFLOW_OIDC_CLIENT_SECRET`은 생성하지 않습니다. 각각 Portal API의 실제 값,
[Keycloak client 등록](03-deploy.md#3-client-등록)의 값을 입력합니다.

### 3. 설정 묶음별 확인

현재 값은 [서버 env](../env/k8s.env)의 선언이며 실제 서버 적용·접속 확인과 구분합니다.

| 묶음 | 변수 | 설정 기준 |
| --- | --- | --- |
| 배치 | `NAMESPACE`, `NODE_NAME` | `airflow`, `khinfow01`(hostname label 값) |
| 이미지 | `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`, `IMAGE_PULL_SECRET` | 현재 `airflow:3.3.2-release-1`. 태그는 `3.3.2-`으로 시작하는 배포별 고유값, 인증 Secret은 대상 namespace에 준비 |
| 내부 DB | `POSTGRES_MODE`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB` | internal, airflow-postgres, 5432, airflow, airflow 유지 |
| 외부 DB | 위 DB 변수와 `POSTGRES_PASSWORD` | external로 지정하고 미리 준비한 DB 연결값 입력 |
| 디스크 | `POSTGRES_HOST_PATH`, `LOGS_HOST_PATH`, `POSTGRES_STORAGE_SIZE`, `LOGS_STORAGE_SIZE` | 서로 겹치지 않는 Worker 절대 경로, Gi/Ti 용량 |
| DB 권한 | `POSTGRES_IMAGE`, `POSTGRES_UID`, `POSTGRES_GID` | 사내 mirror의 PostgreSQL 16 이미지, Debian 이미지 기본 999/999 |
| ODBC | `ODBC_HOST_PATH`, `ODBC_SECRET_NAME` | 둘 중 하나만 사용. 현재 `/appdata/airflow/odbc` |
| 초기 관리자 | `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_ADMIN_EMAIL` | 현재 `airflow`·`admin@admin.com`. 계정이 없을 때만 생성, 기존 계정의 비밀번호는 바꾸지 않음. Keycloak 관리자 `etch-admin`과 구분 |
| 암호화 | `AIRFLOW_FERNET_KEY`, `AIRFLOW_WEBSERVER_SECRET_KEY` | 기존 값 보존, env 전체를 DB 백업과 함께 보관. 웹서버 키는 세션·JWT 서명에 쓰이며 `airflow-api-key`·`airflow-api-jwt`로 전달 |
| Portal | `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN` | 현재 `http://api.tailwind-internal.svc.cluster.local:8000`. token은 Portal API의 같은 변수와 일치 |
| 인증 | `AIRFLOW_AUTH_MODE`, `AIRFLOW_OIDC_*` | [Keycloak 입력](#5-keycloak-sso-입력) |
| 메신저 알림 | `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS` | [실패 알림](#실패-알림-입력) |
| 메일 알림 | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID`, `AIRFLOW_FAILURE_ALERT_EMAIL_FROM`, `AIRFLOW_FAILURE_ALERT_EMAIL_TO` | [실패 알림](#실패-알림-입력) |

외부 DB 모드는 내부 PostgreSQL workload와 DB PV를 만들지 않으며 로그 PV는 유지합니다. DB 이전·기존 리소스 삭제는 자동으로 하지 않습니다.
외부 모드에서도 입력 검사에 필요한 `POSTGRES_IMAGE`, 디스크 경로·용량·UID/GID 항목은 파일에서 제거하지 않습니다.

### 4. 접속 방식 선택

| 방식 | env 설정 | 배포 전 준비 |
| --- | --- | --- |
| 기존 공용 Traefik(운영 기본) | `INGRESS_ENABLED=true`, `INGRESS_CLASS_NAME=traefik`, `AIRFLOW_WEBSERVER_BASE_URL=https://airflow.etch.samsungds.net` | `etch-sso/traefik`, DNS, 공용 저장소에 등록한 도메인 인증서 |
| port-forward | `INGRESS_ENABLED=false`, `AIRFLOW_WEBSERVER_BASE_URL=http://localhost:8080` | 클러스터 접근 권한 |

운영 공개 URL에는 앱 접두사를 붙이지 않으며 Ingress와 앱은 루트 경로(`/`)를 사용합니다.
인증서는 `etch-sso/traefik-tls`에서 관리하므로 기본 env에 앱별 TLS Secret 입력은 없습니다.
`make airflow-up`은 공용 Traefik과 HTTPS를 전제로 합니다. 다른 Ingress controller를 쓰는 경우에만 env에 `INGRESS_TLS_SECRET`을 추가하고
같은 namespace의 TLS Secret을 준비한 뒤 [직접 deploy](03-deploy.md#7-고급-직접-deploy와-helm-override)를 사용합니다.
공용 인증서 등록은 [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)을 따릅니다.

### 5. Keycloak SSO 입력

기본 `AIRFLOW_AUTH_MODE=keycloak`에는 issuer·전용 client ID/secret이 필요합니다. 입력표·CA·client 등록은
[Keycloak 로그인](03-deploy.md#keycloak-로그인)을 따릅니다.
`AIRFLOW_OIDC_ALLOW_HTTP=true`는 공개 주소가 localhost인 개발 환경에서만 허용합니다.
`replace-me`·`replace-here` 같은 자리표시자가 남으면 실제 입력 검사에서 중단합니다.
`AIRFLOW_AUTH_MODE=db`는 기존 DB 로그인이 필요한 복구 상황에서만 명시적으로 사용합니다.

### 6. 다른 env 파일 사용

Makefile에는 `AIRFLOW_ENV`, Python 도구에는 `--env`로 같은 파일을 매번 전달합니다. 아래 두 명령은 설정이나 클러스터를 변경하지 않으며
[chart 준비](02-artifacts.md#1-공식-chart-준비) 후에 실행합니다.

```bash
read -r -p '사용할 env 절대 경로: ' AIRFLOW_ENV_FILE
python3 deploy/airflow/scripts/manage.py check --env "$AIRFLOW_ENV_FILE" --pause-new-dags
make airflow-check KUBE_CONTEXT=kubernetes-admin@kubernetes AIRFLOW_ENV="$AIRFLOW_ENV_FILE"
```

**완료 기준:** 초기 비밀값·Portal trigger token·OIDC client secret이 준비되고 자리표시자가 실제 입력으로 바뀌었습니다.
**다음 단계:** [chart·이미지·ODBC 준비](02-artifacts.md).

### 실패 알림 입력

업무 DAG에 연결된 `notify_airflow_task_failure`가 Task 실패 시 메신저·메일을 각각 시도합니다.
수신자를 비운 채널은 생략하고, 한쪽이 실패해도 다른 쪽은 계속 시도합니다. 알림 실패는 callback 로그에 남으며 원래 Task 실패를 덮어쓰지 않습니다.
재시도 후 최종 성공한 Task나 클러스터·Pod 장애 감시는 이 callback의 범위가 아닙니다.

| 채널 | 필요한 입력 |
| --- | --- |
| 메신저 | `KNOX_MESSENGER_*` 세 값과 쉼표로 구분한 `AIRFLOW_FAILURE_ALERT_KNOX_IDS` |
| 메일 | `MAIL_API_URL`: 발송 API 전체 URL, `MAIL_API_KEY`: `x-dep-ticket`, `MAIL_API_SYSTEM_ID`: `systemId`, `MAIL_API_KNOX_ID`: `loginUser.login` |
| 메일 발신·수신 | `AIRFLOW_FAILURE_ALERT_EMAIL_FROM`: 발송 권한이 있는 이메일, `AIRFLOW_FAILURE_ALERT_EMAIL_TO`: 쉼표로 구분한 이메일 목록 |

메일은 SMTP 대신 기존 Knox Mail HTTP API를 호출합니다. `MAIL_API_*`는 Portal과 같은 요청 형식이지만 Airflow Pod에 별도로 주입합니다.
`MAIL_API_URL`의 기존 query는 유지하고 `systemId`·`loginUser.login`은 env 값으로 대체합니다.
메일 수신자를 설정하면 배포 도구가 필수 입력·URL·이메일 형식을 검사합니다. 메일 키가 없는 외부 env는 메일 미사용으로 처리합니다.

env 값은 `airflow-runtime` Secret을 통해 Pod 환경변수로 전달되므로 편집 후 재배포해야 반영됩니다.
`failure_alerts.py` 코드 변경은 새 이미지 태그가 필요합니다([DAG·이미지 업데이트](04-operations.md#4-dag이미지-업데이트)).
API 연결·발송 권한과 실제 수신은 서버에서 따로 확인합니다.
