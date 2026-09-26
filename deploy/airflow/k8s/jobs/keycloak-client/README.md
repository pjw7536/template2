# Airflow Keycloak SSO 등록과 운영

기존 Keycloak realm에 Airflow 전용 confidential client를 등록합니다.
로그인한 모든 사용자는 기본 Viewer입니다. 필요한 운영자에게만 Keycloak 사용자 화면에서
`airflow` client의 `User` 또는 `Admin` 역할을 직접 부여합니다. 조직별 그룹은 사용하지 않습니다.
역할을 제거하면 다음 로그인부터 Viewer로 돌아갑니다. 기존 세션 이관·통합 로그아웃은 범위 밖입니다.

## 1. 실제 env와 이미지 준비

SSO 코드를 포함한 Airflow 2.11.0 이미지를 새 고유 태그로 빌드합니다.
공개 예시를 복사한 Git 제외 운영 env를 사용하고 아래 값을 입력합니다.
기존 DB·Fernet 키·관리자 API 계정은 유지합니다.

| 키 | 입력 |
| --- | --- |
| `AIRFLOW_AUTH_MODE` | `keycloak` |
| `AIRFLOW_OIDC_ISSUER` | 기존 realm의 공개 HTTPS issuer, 끝은 `/realms/<realm>` |
| `AIRFLOW_OIDC_CLIENT_ID` | `airflow` |
| `AIRFLOW_OIDC_CLIENT_SECRET` | 신규 client용 강한 비밀값. 기존 client가 있으면 기존 secret |
| `AIRFLOW_OIDC_BACKCHANNEL_BASE_URL` | Pod 접근용 realm URL, 비우면 issuer 사용 |
| `AIRFLOW_OIDC_CA_CONFIGMAP` | 사내 CA가 필요하면 Airflow namespace의 ConfigMap 이름 |
| `AIRFLOW_OIDC_CA_BUNDLE` | CA 사용 시 `/etc/airflow/oidc-ca/ca.crt`, 아니면 빈 값 |
| `AIRFLOW_OIDC_ALLOW_HTTP` | 서버는 `false` |

CA ConfigMap은 `ca.crt` 키에 필요한 신뢰 루트·중간 CA를 포함한 bundle을 넣습니다.
CA 설정을 쓰면 TLS 인증서 검증에 해당 bundle을 사용합니다. HTTPS 검증 생략은 지원하지 않습니다.
브라우저 callback은 `${AIRFLOW_WEBSERVER_BASE_URL}/oauth-authorized/keycloak` 하나만 등록합니다.
운영 Airflow 공개 URL은 `https://etch.samsungds.net/airflow`이며, callback은
`https://etch.samsungds.net/airflow/oauth-authorized/keycloak`입니다.
현재 realm issuer는 `https://etch-sso.samsungds.net/realms/etch`입니다.
업무 도메인의 TLS 원본은 `headlamp/headlamp-tls`, Airflow 대상은 `airflow/airflow-tls`이며
[배포 절차](../../../04_SETUP_FLOW.md)에 따라 최초 복사합니다.

## 2. client 등록

저장소 루트에서 실행합니다. Python 표준 라이브러리와 기존 Keycloak 관리자 계정이 필요합니다.
관리자 API URL은 HTTPS 주소 또는 명시적으로 준비한 localhost port-forward 주소입니다.
아래 환경변수는 실행 프로세스 입력이며 Git 추적 파일에 보관하지 않습니다.

```bash
read -r -p 'Keycloak 관리자 API base URL: ' KEYCLOAK_ADMIN_URL
read -r -p 'Keycloak 관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p 'Keycloak 관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD
# 실행 호스트에 사내 CA가 필요하면 KEYCLOAK_ADMIN_CA_BUNDLE에 실제 파일 경로를 export합니다.
make airflow-keycloak-client AIRFLOW_ENV=/절대경로/k8s.env
unset KEYCLOAK_ADMIN_PASSWORD
```

등록기는 master realm의 admin-cli로 관리자 인증한 뒤 대상 realm의 전용 client만 관리합니다.
Authorization Code + PKCE S256, RS256 ID Token, profile·email scope와 전용 client 역할 mapper를 설정합니다.
신규·기존 realm 모두 같은 명령을 사용합니다. 기존 client secret이 env와 다르면 중단하며 회전하지 않습니다.
사용자 역할·기존 realm·타 앱 client는 유지하고 운영 사용자에게 권한을 자동 부여하지 않습니다.

관리자 UI에서 필요한 사용자에게 `airflow`의 `Admin` 또는 `User`를 직접 부여합니다.
조회 사용자는 별도 할당이 필요 없습니다. `portal` client의 역할은 Airflow 자체 권한이 아닙니다.

## 3. 검사·배포·검증

기존 [배포 흐름](../../../04_SETUP_FLOW.md)에 같은 운영 env를 전달합니다.

```bash
python3 deploy/airflow/scripts/manage.py check --env /절대경로/k8s.env --pause-new-dags
make airflow-check AIRFLOW_ENV=/절대경로/k8s.env KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
make airflow-up AIRFLOW_ENV=/절대경로/k8s.env KUBE_CONTEXT="$AIRFLOW_KUBE_CONTEXT"
```

Airflow 로그인 화면의 Keycloak 버튼으로 로그인합니다. 기본 사용자의 DAG 조회·관리 작업 거부,
관리자의 관리 화면 접근, User·Admin 제거 후 새 로그인에서 Viewer 복귀를 확인합니다.
잘못된 토큰·다른 issuer·만료 토큰은 기본 Viewer로 처리하지 않고 로그인에 실패해야 합니다.

Portal → Airflow는 기존 DB 계정의 Basic 인증을 유지합니다. 웹 로그인만 SSO로 바뀌며
Airflow → Portal의 trigger token도 바뀌지 않습니다. 양방향 호출을 별도로 검증합니다.
현재 Portal API에 쓰는 관리자 계정의 최소 권한 전용 계정 전환은 후속 작업입니다.

문제 시 `AIRFLOW_AUTH_MODE=db`로 명시적으로 되돌려 재배포할 수 있습니다.
DB·Fernet 키·기존 API 계정을 초기화하지 않습니다. 서버 env·client를 준비하지 않은 로컬 성공을
서버 SSO 적용 완료로 간주하지 않습니다.
