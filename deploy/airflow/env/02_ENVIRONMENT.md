# 02. Airflow 환경변수

[시작 안내](../README.md) · 이전: [서버 준비](../01_SERVER_SETUP.md) · 다음: [차트·이미지](../03_ARTIFACTS.md)

## 1. 입력 파일 선택

| 파일 | 읽는 명령 | 목적 |
| --- | --- | --- |
| `deploy/airflow/env/k8s.env` | check·render·deploy·build-image, airflow-check·airflow-up | 서버·이미지 태그·접속 URL·Secret 입력 |
| `deploy/airflow/env/build.env` | build-image의 `--build-env` | 기본 이미지·APT/PIP mirror·ODBC 설치 입력 |
| `deploy/airflow/helm/values.yaml` | check·render·deploy | 공통 자원·Executor·로그 보관 정책 |

현재 저장소는 두 env 파일을 Git에서 관리합니다. 실제 비밀값을 문서나 Helm override에 복사하지 않습니다.
env는 셸 스크립트가 아니라 데이터입니다. `source`로 읽지 말고 따옴표 없는 `KEY=값`을 사용합니다.
값 안의 `$VAR`와 `$(...)`는 확장되지 않습니다.

## 2. 최초 설치의 키 생성

**새 DB를 사용하는 최초 설치이며 비밀값이 모두 비어 있을 때만** 실행합니다.
기존 배포의 env가 준비되어 있으면 이 명령을 건너뛰고 기존 값을 유지합니다.

```bash
python3 deploy/airflow/scripts/manage.py init-secrets \
  --env deploy/airflow/env/k8s.env
chmod 600 deploy/airflow/env/k8s.env
```

`init-secrets`는 `env/k8s.env`에 DB 비밀번호·관리자 비밀번호·Fernet 키·웹서버 키를 생성하고 파일 권한을 0600으로 설정합니다. 기존 키가 있으면 재생성을 거부하며 일반 설정은 보존합니다.
다음 값을 실제 환경에 맞게 편집합니다.

- `NODE_NAME`: 노드의 `kubernetes.io/hostname` label 값. Airflow Pod와 내부 DB·local PV가 이 노드에 묶입니다.
- `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`: 배포할 DAG 포함 이미지. 매 배포마다 고유 태그를 사용합니다.
- `POSTGRES_IMAGE`: 기존 사내 PostgreSQL 16 이미지 주소가 기본 입력되어 있습니다. mirror가 바뀐 경우에만 수정합니다.
- `POSTGRES_UID`, `POSTGRES_GID`: 해당 이미지 사용자 UID/GID. 공식 Debian 이미지 기본값은 999/999입니다.
- `ODBC_HOST_PATH`: 서버의 ODBC 설정 디렉터리 절대 경로. 기본 예시는 `/srv/airflow/odbc`입니다.
- `AIRFLOW_ADMIN_EMAIL`: 실제 관리자 이메일. 생성된 관리자 비밀번호는 `k8s.env`에서 확인합니다.
- `AIRFLOW_API_BASE_URL`: Airflow DAG가 호출하는 Portal API 주소. 다른 namespace라면 Service DNS를 수정합니다.
- `AIRFLOW_TRIGGER_TOKEN`: `k8s.env`에 넣습니다. Portal API의 동일 변수와 일치시키며 새로 임의 생성하지 않습니다.
- `AIRFLOW_WEBSERVER_BASE_URL`: `/airflow`로 끝나는 접속 URL. port-forward 접속 예시는 `http://localhost:8080/airflow`입니다.

Knox 연결과 실패 알림이 필요하면 같은 파일의 `KNOX_*`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS`를 채웁니다.
단, `KNOX_MESSENGER_AUTHORIZATION`은 `k8s.env`에 저장합니다.
설정은 따옴표 없이 `KEY=값`으로 작성하며 `$VAR`, `$(...)`를 실행하거나 확장하지 않습니다.
다른 설정 파일을 쓰는 방법은 아래 5단계를 따릅니다.

기존 파일의 일반 설정은 유지하며 비어 있는 비밀값을 채웁니다. 기존 비밀값이 하나라도 있으면 중단합니다.
`AIRFLOW_TRIGGER_TOKEN`은 생성하지 않으므로 Portal에서 사용하는 실제 값을 직접 맞춥니다.
완료 기준: 네 초기 비밀값과 Portal trigger token이 준비되고 예시값이 실제 입력으로 바뀌어야 합니다.

## 3. 설정 묶음별 확인

| 묶음 | 변수 | 설정 기준 |
| --- | --- | --- |
| 배치 | `NAMESPACE`, `NODE_NAME` | namespace 기본 예시는 airflow, 노드는 hostname label 값 |
| 이미지 | `AIRFLOW_IMAGE_REPOSITORY`, `AIRFLOW_IMAGE_TAG`, `IMAGE_PULL_SECRET` | 태그는 `2.11.0-`으로 시작하는 고유값, 인증 Secret은 대상 namespace에 준비 |
| 내부 DB | `POSTGRES_MODE`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB` | internal, airflow-postgres, 5432, airflow, airflow 유지 |
| 외부 DB | 위 DB 변수와 `POSTGRES_PASSWORD` | external로 지정하고 미리 준비한 DB 연결값 입력 |
| 디스크 | `POSTGRES_HOST_PATH`, `LOGS_HOST_PATH`, `POSTGRES_STORAGE_SIZE`, `LOGS_STORAGE_SIZE` | 서로 겹치지 않는 Worker 절대 경로, Gi/Ti 용량 |
| DB 권한 | `POSTGRES_IMAGE`, `POSTGRES_UID`, `POSTGRES_GID` | PostgreSQL 16 이미지와 실제 실행 UID/GID |
| ODBC | `ODBC_HOST_PATH`, `ODBC_SECRET_NAME` | 호스트 디렉터리 또는 기존 Secret 중 하나 사용 |
| 초기 관리자 | `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`, `AIRFLOW_ADMIN_EMAIL` | 계정이 없을 때 생성, 기존 계정의 비밀번호는 바꾸지 않음 |
| 암호화 | `AIRFLOW_FERNET_KEY`, `AIRFLOW_WEBSERVER_SECRET_KEY` | 기존 배포 값 보존, env 전체를 DB 백업과 함께 보관 |
| Portal | `AIRFLOW_API_BASE_URL`, `AIRFLOW_TRIGGER_TOKEN` | Airflow → Portal 호출 주소·공유 token |
| 알림 | `KNOX_MESSENGER_API_BASE_URL`, `KNOX_MESSENGER_AUTHORIZATION`, `KNOX_MESSENGER_SYSTEM_ID`, `AIRFLOW_FAILURE_ALERT_KNOX_IDS` | Knox 연동 시 입력 |

외부 DB 모드는 내부 PostgreSQL workload와 DB PV를 생성하지 않습니다. 로그 PV는 유지합니다.
DB 이전·기존 리소스 삭제를 자동으로 수행하지 않습니다. 외부 모드에서도 현재 입력 검사에 필요한
`POSTGRES_IMAGE`, 디스크 경로·용량·UID/GID 항목은 파일에서 제거하지 않습니다.

## 4. 접속 방식 선택

| 방식 | env 설정 | 배포 전 준비 |
| --- | --- | --- |
| port-forward | `INGRESS_ENABLED=false`, `AIRFLOW_WEBSERVER_BASE_URL=http://localhost:8080/airflow` | 클러스터 접근 권한 |
| 기존 공용 Traefik | `INGRESS_ENABLED=true`, `INGRESS_CLASS_NAME=traefik`, HTTPS `/airflow` URL, `INGRESS_TLS_SECRET` | `etch-sso/traefik`, DNS, 해당 도메인의 TLS Secret |

`make airflow-up`의 Ingress 경로는 기존 공용 Traefik과 HTTPS를 전제로 합니다.
다른 controller를 사용할 때는 [직접 실행](../04_SETUP_FLOW.md#6-고급-직접-deploy와-helm-override)의 준비 범위를 확인합니다.
URL 경로는 정확히 `/airflow`이며 마지막에 `/`를 덧붙이지 않습니다.

## 5. 다른 env 파일 사용

Makefile에는 `AIRFLOW_ENV`, Python 도구에는 `--env`를 매번 전달합니다.

```bash
read -r -p '사용할 env 절대 경로: ' AIRFLOW_ENV_FILE
python3 deploy/airflow/scripts/manage.py check --env "$AIRFLOW_ENV_FILE" --pause-new-dags
make airflow-check KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT" AIRFLOW_ENV="$AIRFLOW_ENV_FILE"
```

실제 값 검사는 [차트 준비](../03_ARTIFACTS.md) 이후 실행합니다. 위 두 명령은 설정이나 클러스터를 변경하지 않습니다.
