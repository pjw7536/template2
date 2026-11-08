# Airflow 환경변수

[시작 안내](../README.md) · 이전: [서버 준비](01-setup.md) · 다음: [차트·이미지](03-artifacts.md)

## 1. 입력 파일 선택

| 파일 | 읽는 명령 | 목적 |
| --- | --- | --- |
| `deploy/airflow/env/k8s.env` | check·render·deploy·build-image, airflow-check·airflow-up | 서버·이미지 태그·접속 URL·Secret 입력 |
| `deploy/airflow/env/build.env` | build-image의 `--build-env` | 기본 이미지·APT/PIP mirror·ODBC 설치 입력 |
| `deploy/airflow/helm/values.yaml` | check·render·deploy | 공통 자원·Executor·로그 보관 정책 |

두 env 파일은 Git에서 관리합니다. 실제 비밀값은 env에만 넣고 문서나 Helm override에 복사하지 않습니다.

한 줄에 하나씩, 따옴표 없는 `KEY=값`으로 적습니다.
env는 데이터 파일이므로 `source`로 실행하지 않습니다. 값 안의 `$VAR`와 `$(...)`도 확장되지 않습니다.

## 2. 최초 설치의 키 생성

**새 DB를 사용하는 최초 설치이며 비밀값이 모두 비어 있을 때만** 실행합니다.
기존 배포의 env가 준비되어 있으면 이 명령을 건너뛰고 기존 값을 유지합니다.

```bash
python3 deploy/airflow/scripts/manage.py init-secrets \
  --env deploy/airflow/env/k8s.env
chmod 600 deploy/airflow/env/k8s.env
```

`init-secrets`는 `env/k8s.env`에 DB 비밀번호·관리자 비밀번호·Fernet 키·웹서버 키를 만들고
파일 권한을 0600으로 설정합니다. 기존 키가 하나라도 있으면 재생성을 거부합니다.
일반 설정은 그대로 보존합니다.

키 준비 후에는 다음 값을 실제 환경에 맞게 편집합니다.

- `NODE_NAME`: 노드의 `kubernetes.io/hostname` label 값. Airflow Pod와 내부 DB·local PV가 이 노드에 묶입니다.
- `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`: 배포할 DAG 포함 이미지. 매 배포마다 고유 태그를 사용합니다.
- `POSTGRES_IMAGE`: 기존 사내 PostgreSQL 16 이미지 주소가 기본 입력되어 있습니다. mirror가 바뀐 경우에만 수정합니다.
- `POSTGRES_UID`, `POSTGRES_GID`: 해당 이미지 사용자 UID/GID. 공식 Debian 이미지 기본값은 999/999입니다.
- `ODBC_HOST_PATH`: 서버의 ODBC 설정 디렉터리 절대 경로. 기본 예시는 `/appdata/airflow/odbc`입니다.
- `AIRFLOW_ADMIN_EMAIL`: 실제 관리자 이메일. 생성된 관리자 비밀번호는 `k8s.env`에서 확인합니다.
- `AIRFLOW_API_BASE_URL`: Airflow DAG가 호출하는 Portal API 주소. 다른 namespace라면 Service DNS를 수정합니다.
- `AIRFLOW_TRIGGER_TOKEN`: `k8s.env`에 넣습니다. Portal API의 동일 변수와 일치시키며 새로 임의 생성하지 않습니다.
- `AIRFLOW_WEBSERVER_BASE_URL`: `/airflow`로 끝나는 접속 URL. port-forward 접속 예시는 `http://localhost:8080/airflow`입니다.
- `AIRFLOW_WEBSERVER_SECRET_KEY`: API server의 세션과 JWT 서명에 사용하는 고정 비밀값입니다. `airflow-api-key`·`airflow-api-jwt` Secret으로 전달하며 모든 구성 요소가 같은 값을 사용합니다.

실패 알림은 아래 [메신저·메일 실패 알림](#메신저메일-실패-알림)에 따라 같은 파일의 채널별 입력을 채웁니다.
실제 발송 credential은 `k8s.env`에 저장합니다.
설정은 따옴표 없이 `KEY=값`으로 작성하며 `$VAR`, `$(...)`를 실행하거나 확장하지 않습니다.
다른 설정 파일을 쓰는 방법은 아래 5단계를 따릅니다.

기존 파일의 일반 설정은 유지하며 비어 있는 비밀값을 채웁니다. 기존 비밀값이 하나라도 있으면 중단합니다.
`AIRFLOW_TRIGGER_TOKEN`은 생성하지 않으므로 Portal에서 사용하는 실제 값을 직접 맞춥니다.
완료 기준: 네 초기 비밀값과 Portal trigger token이 준비되고 예시값이 실제 입력으로 바뀌어야 합니다.

### Keycloak SSO의 client와 secret 준비

기본 설정인 `AIRFLOW_AUTH_MODE=keycloak`에서는 기존 realm에 Airflow 전용 `airflow` client가 필요합니다.
`init-secrets`는 `AIRFLOW_OIDC_CLIENT_SECRET`을 생성하지 않습니다.
신규 client라면 강한 비밀값을 생성해 같은 env의 `AIRFLOW_OIDC_CLIENT_SECRET`에 입력하고,
Keycloak 관리자 입력을 준비한 뒤 `make airflow-keycloak-client`를 실행합니다.
이 명령이 client와 callback·역할·mapper를 등록하므로 관리자 화면에서 client를 먼저 만들 필요는 없습니다.
이미 client가 있다면 기존 secret을 env에 입력합니다. 새로 생성하거나 회전하지 않습니다.

생성 명령과 관리자 입력·등록 순서는 [Airflow SSO 등록](04-sso.md#2-client-등록)을 따릅니다.
다른 env를 사용하면 `AIRFLOW_ENV`로 같은 파일을 전달합니다.
완료 기준: env와 Keycloak client의 secret이 일치하고 전용 client 등록이 완료되어야 합니다.

## 3. 설정 묶음별 확인

| 묶음 | 변수 | 설정 기준 |
| --- | --- | --- |
| 배치 | `NAMESPACE`, `NODE_NAME` | namespace 기본 예시는 airflow, 노드는 hostname label 값 |
| 이미지 | `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`, `IMAGE_PULL_SECRET` | 태그는 `3.3.2-`으로 시작하는 고유값, 인증 Secret은 대상 namespace에 준비 |
| 내부 DB | `POSTGRES_MODE`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB` | internal, airflow-postgres, 5432, airflow, airflow 유지 |
| 외부 DB | 위 DB 변수와 `POSTGRES_PASSWORD` | external로 지정하고 미리 준비한 DB 연결값 입력 |
| 디스크 | `POSTGRES_HOST_PATH`, `LOGS_HOST_PATH`, `POSTGRES_STORAGE_SIZE`, `LOGS_STORAGE_SIZE` | 서로 겹치지 않는 Worker 절대 경로, Gi/Ti 용량 |
| DB 권한 | `POSTGRES_IMAGE`, `POSTGRES_UID`, `POSTGRES_GID` | PostgreSQL 16 이미지와 실제 실행 UID/GID |
| ODBC | `ODBC_HOST_PATH`, `ODBC_SECRET_NAME` | 호스트 디렉터리 또는 기존 Secret 중 하나 사용 |
| 초기 관리자 | `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_ADMIN_EMAIL` | 계정이 없을 때 생성, 기존 계정의 비밀번호는 바꾸지 않음 |
| 암호화 | `AIRFLOW_FERNET_KEY`, `AIRFLOW_WEBSERVER_SECRET_KEY` | 기존 배포 값 보존, env 전체를 DB 백업과 함께 보관 |
| Portal | `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN` | Airflow → Portal 호출 주소·공유 token |
| 메신저 알림 | `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS` | 수신자 Knox ID는 쉼표로 구분 |
| 메일 알림 | `MAIL_API_URL`, `MAIL_API_KEY`, `MAIL_API_SYSTEM_ID`, `MAIL_API_KNOX_ID`, `AIRFLOW_FAILURE_ALERT_EMAIL_FROM`, `AIRFLOW_FAILURE_ALERT_EMAIL_TO` | 기존 Knox Mail API 계약 사용, 수신자 이메일은 쉼표로 구분 |

외부 DB 모드는 내부 PostgreSQL workload와 DB PV를 생성하지 않습니다. 로그 PV는 유지합니다.
DB 이전·기존 리소스 삭제를 자동으로 수행하지 않습니다. 외부 모드에서도 현재 입력 검사에 필요한
`POSTGRES_IMAGE`, 디스크 경로·용량·UID/GID 항목은 파일에서 제거하지 않습니다.

### 메신저·메일 실패 알림

업무 DAG에 연결된 `notify_airflow_task_failure`가 Task 실패 시 메신저·메일을 각각 시도합니다.
두 채널의 수신자를 모두 설정하면 둘 다 전송하고, 한쪽이 누락되거나 실패해도 다른 쪽은 계속 시도합니다.
수신자를 비운 채널은 생략합니다. 알림 실패는 callback 로그에 남기며 원래 Task 실패를 덮어쓰지 않습니다.
Task 재시도로 최종 성공한 경우의 재시도 알림이나 클러스터·Pod 장애 감시는 이 callback의 범위가 아닙니다.

| 채널 | 필요한 입력 |
| --- | --- |
| 메신저 | 기존 `KNOX_MESSENGER_*` 세 값과 `AIRFLOW_FAILURE_ALERT_KNOX_IDS` |
| 메일 | `MAIL_API_URL`: 발송 API 전체 URL, `MAIL_API_KEY`: `x-dep-ticket`, `MAIL_API_SYSTEM_ID`: `systemId`, `MAIL_API_KNOX_ID`: `loginUser.login` |
| 메일 발신·수신 | `AIRFLOW_FAILURE_ALERT_EMAIL_FROM`: 발송 권한이 있는 이메일, `AIRFLOW_FAILURE_ALERT_EMAIL_TO`: 쉼표로 구분한 이메일 목록 |

메일은 SMTP 대신 기존 Knox Mail HTTP API를 직접 호출합니다. `MAIL_API_*`는 Portal과 같은 요청 형식이지만
Airflow Pod에 별도로 주입하며 Portal의 env를 자동 상속하지 않습니다. 발송 계정·발신자 권한은 실제 API에서 확인합니다.
`MAIL_API_URL`의 기존 query를 유지하며 `systemId`·`loginUser.login`은 각각
`MAIL_API_SYSTEM_ID`·`MAIL_API_KNOX_ID`의 값으로 대체하여 중복 없이 전송합니다.
메일 수신자를 설정하면 배포 도구가 필수 입력·URL·이메일 형식을 검사합니다.
새 메일 키가 없는 기존 외부 env는 메일 미사용 기본값으로 처리합니다.

`failure_alerts.py`는 DAG와 함께 이미지에 포함됩니다. 코드 변경 후 새 이미지 태그로 빌드·전달하고
검사·배포해야 합니다. env 값은 `airflow-runtime` Secret을 통해 Pod 환경변수로 전달되며
env만 편집하면 실행 중인 Pod에 반영되지 않습니다. [업데이트 절차](06-operations.md#3-dag이미지-업데이트)를 따릅니다.
메일 본문에는 DAG·Task·실행 ID·오류·로그 링크가 포함됩니다. 두 API의 연결·발송 권한과 실제 수신은 서버에서 따로 확인합니다.

로컬 실행 도구는 `local/portal/env/api.env`의 Mail sandbox 입력을 재사용하고 기본 수신자는 비웁니다.
메일 알림을 로컬에서 시험할 때는 `local/shared/env/k8s.env`의 `LOCAL_AIRFLOW_FAILURE_ALERT_EMAIL_TO`에 수신자를 지정하고
mock의 `/mail/messages`에서 결과를 확인합니다. 운영 credential을 로컬 입력에 복사하지 않습니다.

## 4. 접속 방식 선택

| 방식 | env 설정 | 배포 전 준비 |
| --- | --- | --- |
| port-forward | `INGRESS_ENABLED=false`, `AIRFLOW_WEBSERVER_BASE_URL=http://localhost:8080/airflow` | 클러스터 접근 권한 |
| 기존 공용 Traefik | `INGRESS_ENABLED=true`, `INGRESS_CLASS_NAME=traefik`, HTTPS `/airflow` URL | `etch-sso/traefik`, DNS, 공용 저장소에 등록한 도메인 인증서 |

`make airflow-up`의 Ingress 경로는 기존 공용 Traefik과 HTTPS를 전제로 합니다.
다른 controller를 사용할 때는 [직접 실행](05-deploy.md#6-고급-직접-deploy와-helm-override)의 준비 범위를 확인합니다.
URL 경로는 정확히 `/airflow`이며 마지막에 `/`를 덧붙이지 않습니다.

운영 HTTPS 설정은 다음 값으로 통일합니다. namespace는 `airflow`를 사용합니다.
저장소 기본 env에도 이 값과 Keycloak 인증 모드가 설정되어 있습니다.

```dotenv
INGRESS_ENABLED=true
INGRESS_CLASS_NAME=traefik
INGRESS_TLS_SECRET=
AIRFLOW_WEBSERVER_BASE_URL=https://etch.samsungds.net/airflow
```

인증서는 `etch-sso/traefik-tls`에서 관리합니다. `INGRESS_TLS_SECRET`은 기존 env 호환용이며
공용 Traefik에서는 사용하지 않습니다. 다른 Ingress controller의 HTTPS에는 앱별 Secret 이름이 필요합니다.
[공용 TLS 등록](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)을 따릅니다.

## 5. 다른 env 파일 사용

Makefile에는 `AIRFLOW_ENV`, Python 도구에는 `--env`를 매번 전달합니다.

```bash
read -r -p '사용할 env 절대 경로: ' AIRFLOW_ENV_FILE
python3 deploy/airflow/scripts/manage.py check --env "$AIRFLOW_ENV_FILE" --pause-new-dags
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_ENV="$AIRFLOW_ENV_FILE"
```

실제 값 검사는 [차트 준비](03-artifacts.md) 이후 실행합니다. 위 두 명령은 설정이나 클러스터를 변경하지 않습니다.

## Keycloak SSO 입력

기본 `AIRFLOW_AUTH_MODE=keycloak`에는 issuer·전용 client ID/secret이 필요합니다.
[SSO 등록 안내](04-sso.md)의 설정표와 등록 순서를 따릅니다.
서버는 HTTPS를 사용하고 사내 CA는 `AIRFLOW_OIDC_CA_CONFIGMAP`의 `ca.crt`를
`AIRFLOW_OIDC_CA_BUNDLE=/etc/airflow/oidc-ca/ca.crt`로 마운트합니다.
`AIRFLOW_OIDC_ALLOW_HTTP=true`는 공개 Airflow 주소가 localhost인 개발 환경에서만 허용합니다.

## Keycloak 로그인

[SSO 설정·client 등록·검증 안내](04-sso.md)를 따릅니다.
로그인에 성공한 사용자는 기본적으로 Viewer입니다.
추가 권한이 필요하면 Keycloak의 `airflow` client에서 User 또는 Admin 역할을 부여합니다.

저장소 env는 `https://etch.samsungds.net/airflow`와 `AIRFLOW_AUTH_MODE=keycloak`을 기본으로 사용합니다.
배포 전에 전용 client secret과 필요한 CA를 준비합니다. `replace-me`가 남으면 실제 입력 검사에서 중단합니다.
기존 DB 로그인이 필요한 복구 상황에서만 `AIRFLOW_AUTH_MODE=db`로 명시적으로 바꿉니다.
로컬에서는 실행 도구가 localhost 주소와 로컬 Keycloak 입력을 적용합니다.
