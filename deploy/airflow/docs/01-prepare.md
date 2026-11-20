# Airflow 서버 준비와 환경설정

[Airflow 가이드](../README.md)

설치·업데이트 절차는 [Airflow 가이드](../README.md)에 있습니다. 이 문서는 실행 Worker의 조건과 env 입력의 의미·형식입니다.

- [서버 준비](#서버-준비)
- [환경설정](#환경설정)

## 서버 준비

### 필요 도구와 버전

관리 호스트에 Python 3.10 이상, Helm 3.19.0 이상, kubectl, 클러스터 관리자 kubeconfig가 필요합니다. chart가 요구하는 Kubernetes 최소 버전은 1.30.13입니다.
이미지 빌드와 사내 이미지 저장소 push도 같은 checkout에서 수행하므로 [이미지 준비](02-artifacts.md#2-이미지-준비)의 빌더가 필요합니다. 빌더는 `make ops-deploy`의 준비 검사가 확인하고 없으면 설치합니다.

[조회]
```bash
python3 --version
helm version --short
kubectl --context "<context>" version
kubectl --context "<context>" get nodes -L kubernetes.io/hostname
```

성공: 도구가 최소 버전을 충족하고 선택한 context의 노드가 조회됩니다.
현재 클러스터 구성과 다른 앱의 배치는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 확인합니다.
빈 서버를 새 Worker로 추가하려면 [Worker 추가](../../shared/docs/kubernetes/worker.md)를 먼저 진행합니다.
배포 도구는 Kubernetes나 Ingress controller를 설치하지 않습니다.

### 실행 Worker 선택

`NODE_NAME`에는 위 출력의 `kubernetes.io/hostname` 값을 그대로 사용합니다. 현재 선언은 `khinfow01`입니다.
Airflow Pod·내부 DB·local PV가 이 노드에 묶이므로 자원·디스크·ODBC 접근을 만족하는 Worker를 선택합니다.
단일 Worker 구성이므로 해당 Worker나 디스크에 장애가 나면 Airflow가 중단됩니다.

최초 설치는 새 DB·전용 계정·Fernet 키를 사용합니다. 재배포는 사용 중인 DB 비밀번호·Fernet 키를 유지하며,
데이터 이전이 필요하면 [백업·이전](04-operations.md)을 따릅니다.
기존 Kubernetes 설치가 `/srv/airflow`를 사용한다면 이전 완료 전까지 env의 기존 경로를 유지하고,
`/appdata/airflow`로 바꿀 때는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 따릅니다.

### Worker 폴더 직접 준비

`airflow-up`이 env에 선언한 PostgreSQL·로그·DAG·ODBC 폴더 중 없는 것을 아래 소유자·권한으로 만듭니다. 기존 폴더는 바꾸지 않습니다.

| 폴더(현재 선언) | 소유자 | 권한 |
| --- | --- | --- |
| `/appdata/airflow/postgres` | `999:999`(`POSTGRES_UID`·`POSTGRES_GID`) | `0700` |
| `/appdata/airflow/logs` | `50000:0` | `0770` |
| `/appdata/airflow/dags` | `root:root` | `0755` |
| `/appdata/airflow/odbc` | `50000:0` | `0750` |

DAG 폴더는 비어 있는 상태로 만들어지며 파일은 [DAG 파일 추가·수정·삭제](04-operations.md#dag-파일-추가수정삭제)로 넣습니다. DAG가 든 이전 이미지로 실행 중인 설치는 [공유 폴더 전환](04-operations.md#공유-폴더-전환)으로 옮깁니다.
ODBC 폴더의 실제 설정 파일은 [ODBC 파일 안내](../odbc/README.md#worker에-반영)로 배치합니다.

아래 명령은 `airflow-up`을 거치지 않고 폴더를 직접 준비하거나 디스크 여유·권한을 확인할 때만 씁니다. 실행 위치는 **`NODE_NAME`으로 선택한 Worker**(`khinfow01`)이며, 블록을 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다.
경로와 UID/GID는 현재 env 선언 기준이며 실제 env와 일치시킵니다. `POSTGRES_MODE=external`이면 PostgreSQL 경로를 제외합니다.

[변경] 없는 폴더를 만듭니다. 이미 있는 폴더는 소유자와 권한만 아래 값으로 맞춰지므로, 데이터가 든 기존 폴더에는 실행하지 않습니다.

```bash
sudo -n install -d -o 999 -g 999 -m 0700 /appdata/airflow/postgres
sudo -n install -d -o 50000 -g 0 -m 0770 /appdata/airflow/logs
sudo -n install -d -o root -g root -m 0755 /appdata/airflow/dags
```

[조회] 디스크 여유와 소유자·권한을 확인합니다.

```bash
df -h /appdata/airflow/postgres /appdata/airflow/logs /appdata/airflow/dags
sudo -n stat -c '%u:%g %a %n' /appdata/airflow/postgres /appdata/airflow/logs /appdata/airflow/dags
```

성공: 각 경로의 소유자와 권한이 DB `999:999`·`700`, 로그 `50000:0`·`770`, DAG `0:0`·`755`입니다.

- PV에 선언한 용량과 실제 디스크 여유는 별도로 확인합니다.
- 로그는 자동 삭제하지 않습니다. 보관 정책을 정한 뒤 필요하면 `scheduler.logGroomerSidecar`를 설정합니다.
- 기존 Compose PostgreSQL 데이터 폴더를 바로 연결하지 않습니다. [기존 DB 이전](04-operations.md#3-기존-compose-db-이전)을 따릅니다.
- 외부 DB는 미리 생성한 DB·계정으로 Worker에서 접근할 수 있어야 합니다.

## 환경설정

### 입력 파일

| 파일 | 읽는 명령 | 목적 |
| --- | --- | --- |
| `deploy/airflow/env/k8s.env` | init-secrets·check·render·deploy·build-image, airflow-image·airflow-check·airflow-up·airflow-keycloak-client | 서버·이미지 태그·접속 URL·Secret 입력 |
| `deploy/airflow/env/build.env` | build-image·airflow-image의 `--build-env` | 기본 이미지·APT/PIP mirror·ODBC 설치 입력 |
| `deploy/airflow/helm/values.yaml` | check·render·deploy | 공통 자원·Executor·로그 보관 정책 |

두 env 파일은 Git에서 관리합니다. 비밀값은 env에만 넣고 문서나 Helm override에 복사하지 않습니다.
한 줄에 하나씩 따옴표 없는 `KEY=값`으로 적습니다. env는 데이터 파일이므로 `source`하지 않으며 `$VAR`·`$(...)`도 확장되지 않습니다.

### 최초 비밀값 생성

저장소 기본 env에는 신규 설치에 쓸 관리자 비밀번호와 OIDC client secret이 준비되어 있습니다. 기본 env로 설치할 때는 이 절이 필요하지 않습니다.

[변경] **저장소 밖에 별도로 준비한 env에서 새 DB를 사용하는 최초 설치이며 비밀값이 모두 비어 있을 때만** 실행합니다. 저장소의 기본 env와 기존 배포의 비밀값은 유지합니다.

```bash
python3 deploy/airflow/scripts/manage.py init-secrets \
  --env <env 절대 경로>
chmod 600 <env 절대 경로>
```

성공: `env 초기 키 생성 완료`. DB 비밀번호·관리자 비밀번호·Fernet 키·웹서버 키가 생성되고 파일 권한이 0600이 됩니다.
기존 비밀값이 하나라도 있으면 재생성을 거부하며 일반 설정은 보존합니다.
`AIRFLOW_TRIGGER_TOKEN`과 `AIRFLOW_OIDC_CLIENT_SECRET`은 생성하지 않습니다. `AIRFLOW_TRIGGER_TOKEN`에는 Portal API env의 같은 키 값을,
`AIRFLOW_OIDC_CLIENT_SECRET`에는 [Keycloak client 등록](03-deploy.md#client-등록)의 값을 env 파일의 해당 줄에 넣습니다.

**신규 설치의 외부 env에서 일부 비밀값만 비어 있거나 자리표시자인 경우:** `init-secrets`는 거부되므로 해당 키만 생성합니다.
비밀값은 20자 이상이어야 하며 `AIRFLOW_FERNET_KEY`만 32바이트 URL-safe base64 형식입니다. 아래 명령은 생성값을 화면에 출력하지 않고 env 파일의 그 키 줄에 바로 기록합니다. 값이 비어 있거나 자리표시자(`replace-me`·`replace-here`·`change-me`)일 때만 바꾸고, 이미 값이 있는 키는 그대로 둡니다.

[변경] `<키>`를 `AIRFLOW_ADMIN_PASSWORD`, `POSTGRES_PASSWORD`, `AIRFLOW_WEBSERVER_SECRET_KEY` 중 비어 있는 키 이름 하나로 바꿔 키마다 한 번씩 실행합니다.

```bash
sed -i -E "s,^(<키>)=(.*(replace-me|replace-here|change-me).*)?\$,\1=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')," <env 절대 경로>
```

[변경] `AIRFLOW_FERNET_KEY`가 비어 있을 때만 실행합니다. 새 DB의 최초 설치 전용이며, DB가 이미 있는 환경의 키는 절대 바꾸지 않습니다.

```bash
sed -i -E "s,^(AIRFLOW_FERNET_KEY)=(.*(replace-me|replace-here|change-me).*)?\$,\1=$(python3 -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')," <env 절대 경로>
```

실행 후 [실제 입력 검사](#다른-env-파일과-입력-검사)의 `manage.py check`로 `실제 값으로 교체하세요`가 없어졌는지 확인합니다.

### 설정 묶음

현재 값은 [서버 env](../env/k8s.env)의 선언이며 실제 서버 적용·접속 확인과 구분합니다.

| 묶음 | 변수 | 설정 기준 |
| --- | --- | --- |
| 배치 | `NAMESPACE`, `NODE_NAME` | `airflow`, `khinfow01`(hostname label 값) |
| 이미지 | `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`, `IMAGE_PULL_SECRET` | 현재 `store.etch.samsungds.net/airflow`와 `3.3.2-auto`(소스 내용으로 `3.3.2-<12자리>` 자동 결정). 직접 쓰는 태그는 `3.3.2-`으로 시작하는 고유값, 인증 Secret은 대상 namespace에 준비 |
| 내부 DB | `POSTGRES_MODE`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB` | internal, airflow-postgres, 5432, airflow, airflow 유지 |
| 외부 DB | 위 DB 변수와 `POSTGRES_PASSWORD` | external로 지정하고 미리 준비한 DB 연결값 입력 |
| 디스크 | `POSTGRES_HOST_PATH`, `LOGS_HOST_PATH`, `POSTGRES_STORAGE_SIZE`, `LOGS_STORAGE_SIZE` | 서로 겹치지 않는 Worker 절대 경로, Gi/Ti 용량 |
| DAG 공유 | `DAGS_HOST_PATH`, `DAGS_STORAGE_SIZE` | 필수. 운영 선언은 `/appdata/airflow/dags`·`1Gi`. 이미지에는 DAG가 없으므로 Airflow는 이 폴더의 파일만 읽습니다. `airflow-up`은 폴더를 만들기만 하고 파일은 운영자가 관리합니다. 경로를 비우면 검사에서 `DAGS_HOST_PATH가 필요합니다`로 멈춥니다. |
| DB 권한 | `POSTGRES_IMAGE`, `POSTGRES_UID`, `POSTGRES_GID` | 사내 mirror의 PostgreSQL 16 이미지, Debian 이미지 기본 999/999 |
| ODBC | `ODBC_HOST_PATH`, `ODBC_SECRET_NAME` | 둘 중 하나만 사용. 현재 `/appdata/airflow/odbc` |
| 초기 관리자 | `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_ADMIN_EMAIL` | 현재 `airflow`·`admin@admin.com`. 계정이 없을 때만 생성, 기존 계정의 비밀번호는 바꾸지 않음. Keycloak 관리자 `etch-admin`과 구분 |
| 암호화 | `AIRFLOW_FERNET_KEY`, `AIRFLOW_WEBSERVER_SECRET_KEY` | 기존 값 보존, env 전체를 DB 백업과 함께 보관. 웹서버 키는 세션·JWT 서명에 쓰이며 `airflow-api-key`·`airflow-api-jwt`로 전달 |
| Portal | `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN` | 현재 `http://api.tailwind-internal.svc.cluster.local:8000`. token은 Portal API의 같은 변수와 일치 |
| 인증 | `AIRFLOW_AUTH_MODE`, `AIRFLOW_OIDC_*` | [Keycloak SSO 입력](#keycloak-sso-입력) |
| 메신저 알림 | `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS` | [실패 알림](#실패-알림-입력) |
| 메일 알림 | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID`, `AIRFLOW_FAILURE_ALERT_EMAIL_FROM`, `AIRFLOW_FAILURE_ALERT_EMAIL_TO` | [실패 알림](#실패-알림-입력) |

외부 DB 모드는 내부 PostgreSQL workload와 DB PV를 만들지 않으며 로그 PV는 유지합니다. DB 이전·기존 리소스 삭제는 자동으로 하지 않습니다.
외부 모드에서도 입력 검사에 필요한 `POSTGRES_IMAGE`, 디스크 경로·용량·UID/GID 항목은 파일에서 제거하지 않습니다.

### 접속 방식

| 방식 | env 설정 | 배포 전 준비 |
| --- | --- | --- |
| 기존 공용 Traefik(운영 기본) | `INGRESS_ENABLED=true`, `INGRESS_CLASS_NAME=traefik`, `AIRFLOW_WEBSERVER_BASE_URL=https://airflow.etch.samsungds.net` | `etch-sso/traefik`, 공용 저장소에 등록한 도메인 인증서. DNS는 없어도 배포되며 등록이 남은 일로 표시됨 |
| port-forward | `INGRESS_ENABLED=false`, `AIRFLOW_WEBSERVER_BASE_URL=http://localhost:8080` | 클러스터 접근 권한 |

운영 공개 URL에는 앱 접두사를 붙이지 않으며 Ingress와 앱은 루트 경로(`/`)를 사용합니다.
인증서는 `etch-sso/traefik-tls`에서 관리하므로 기본 env에 앱별 TLS Secret 입력은 없습니다.
`INGRESS_ENABLED=true`인 `make airflow-up`은 공용 Traefik(`INGRESS_CLASS_NAME=traefik`)과 HTTPS 공개 URL을 전제로 합니다. 다른 Ingress controller를 쓰는 경우에만 env에 `INGRESS_TLS_SECRET`을 추가하고
같은 namespace의 TLS Secret을 준비한 뒤 [직접 deploy](03-deploy.md#직접-deploy와-helm-override)를 사용합니다.
공용 인증서는 `make ops-deploy`의 준비 검사가 인증서 파일이 있으면 등록합니다. 직접 등록하거나 갱신할 때는 [공용 TLS 등록](../../README.md#공용-tls-등록)을 따릅니다.

### Keycloak SSO 입력

기본 `AIRFLOW_AUTH_MODE=keycloak`에는 issuer·전용 client ID/secret이 필요합니다. 입력표·CA·client 등록은
[Keycloak 로그인](03-deploy.md#keycloak-로그인)을 따릅니다.
`AIRFLOW_OIDC_ALLOW_HTTP=true`는 공개 주소가 localhost인 개발 환경에서만 허용합니다.
`replace-me`·`replace-here` 같은 자리표시자가 남으면 실제 입력 검사에서 중단합니다.
`AIRFLOW_AUTH_MODE=db`는 기존 DB 로그인이 필요한 복구 상황에서만 명시적으로 사용합니다.

### 다른 env 파일과 입력 검사

Makefile에는 `AIRFLOW_ENV`, Python 도구에는 `--env`로 같은 파일을 매번 전달합니다. 저장소 밖 env의 위치와 권한은 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)을 따릅니다. 아래 명령은 설정이나 클러스터를 변경하지 않으며
[chart 준비](02-artifacts.md#1-공식-chart-준비) 후에 실행합니다. 저장소 env를 쓰면 `--env deploy/airflow/env/k8s.env`입니다.

[검사]
```bash
python3 deploy/airflow/scripts/manage.py check --env <env 절대 경로> --pause-new-dags
```

성공: `Airflow Helm·PostgreSQL 원본 검사 통과 (실제 설정; 클러스터 적용 없음)`.
초기 비밀값·Portal trigger token·OIDC client secret이 준비되고 자리표시자가 실제 입력으로 바뀌어야 통과합니다. 클러스터 사전 검사의 범위는 [검사 범위](03-deploy.md#검사-범위)에 있습니다.

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

env 값은 `airflow-runtime` Secret을 통해 Pod 환경변수로 전달되므로 값을 바꾼 뒤 [가이드 B](../README.md#b-업데이트)의 env 행으로 재배포해야 반영됩니다.
`failure_alerts.py` 코드 변경은 새 이미지 태그가 필요합니다([이미지 업데이트](04-operations.md#이미지-업데이트)).
API 연결·발송 권한과 실제 수신은 서버에서 따로 확인합니다.
