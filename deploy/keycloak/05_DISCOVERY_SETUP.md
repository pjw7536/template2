# 05. 사내 OIDC Discovery와 통합 실행

[시작 안내](README.md) · 기본 실행: [0~5단계 설정](04_SETUP_FLOW.md) · 입력: [환경변수 안내](env/02_ENVIRONMENT.md)

이 문서는 **사내 IdP의 접속 정보를 어떻게 가져오는지**, 그리고 여러 단계를 한 번에 실행하는
기존 통합 명령이 어디까지 처리하는지 설명합니다. 한 단계씩 실행할 때는 `04_SETUP_FLOW.md`를 사용하세요.

## 1. Discovery가 자동으로 채우는 값

`CORP_OIDC_DISCOVERY_URL`은 사내 OpenID Connect metadata 문서의 주소입니다.
실행 호스트가 이 JSON을 조회해 Keycloak IdP Job의 입력으로 변환합니다.

| Metadata 항목 | 사용 목적 |
| --- | --- |
| `authorization_endpoint` | 브라우저 사내 인증 주소 |
| `token_endpoint` | 인증 코드를 토큰으로 교환 |
| `issuer` | 토큰 발급자 검증. 받은 값을 그대로 유지 |
| `jwks_uri` | 토큰 서명 검증용 공개키 |
| `userinfo_endpoint` | 추가 사용자 정보 조회. 제공되는 경우 사용 |
| `end_session_endpoint` | 사내 로그아웃. 제공되는 경우 사용 |

통신 endpoint는 HTTPS로 검사하고 서명 검증은 `true`를 요구합니다.
Authorization·Token·issuer·JWKS가 누락되면 중단합니다.
UserInfo/logout은 discovery가 제공하면 사용하고, 없으면 별도로 입력한 env 값을 사용합니다.
둘 다 없으면 기존 IdP의 해당 설정을 보존합니다. 신규 IdP에는 없는 URL을 추정해서 만들지 않습니다.

조회 결과는 비공개 임시 env와 OIDC Secret으로 전달합니다. 원본 `prod.env`는 덮어쓰지 않습니다.
명령을 다시 실행할 때 metadata를 다시 읽으며 실행 사이에 endpoint를 자동 동기화하지는 않습니다.

## 2. 별도로 준비할 발급 정보

Discovery는 client ID·secret·사내 claim 의미·앱 접근 권한을 발급하지 않습니다.
`deploy/keycloak/env/prod.env`에서 아래 입력을 준비합니다.

```dotenv
CORP_OIDC_DISCOVERY_URL=<사내 discovery URL>
CORP_OIDC_CLIENT_ID=<AD FS client ID>
CORP_OIDC_CLIENT_SECRET=<AD FS client secret>
CORP_OIDC_CLIENT_AUTH_METHOD=client_secret_post
CORP_OIDC_VALIDATE_SIGNATURE=true
```

현재 파일에는 discovery URL과 인증 방식이 설정돼 있습니다. client ID·secret을 입력하면 됩니다.
`client_secret_post`는 관리 화면의 `Client secret sent in the request body`에 해당합니다.
Discovery가 여러 인증 방식을 지원해도 실제 client에 맞는 방식을 선택해야 합니다.
지원 방식 목록이 생략된 경우 도구는 `client_secret_basic`을 기본 지원 방식으로 검사합니다.

AD FS에 Authorization Code용 client를 등록할 때 redirect URI는 다음 형태입니다.

```text
<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint
```

Portal callback과 다른 주소입니다. 운영과 별도 환경은 각자 발급된 client와 공개 URL을 사용합니다.

## 3. 실행 위치와 연결 조건

- 호스트에 Python 3·Bash·kubectl이 필요합니다. 단계별 실행 전체의 기준은 Python 3.10+입니다.
- 호스트에서 사내 discovery에 접근하고 인증서를 신뢰해야 합니다. 별도 CA 파일이 필요하면 `SSL_CERT_FILE`을 지정합니다.
- Keycloak 서버도 Token·JWKS·UserInfo 등에 접근하고 인증서를 신뢰해야 합니다. 호스트 CA 설정이 Pod로 자동 전파되지는 않습니다.
- `etch` realm과 실제 관리자 credential이 준비돼 있어야 합니다. Realm은 [0번 단계](04_SETUP_FLOW.md#0-realm-생성)에서 준비합니다.

### 3-1. 저장소 루트로 이동하고 도구 확인

Keycloak 서버 설치를 마친 운영 호스트에서 터미널을 엽니다. 아래 경로에는 실제 저장소 위치를 입력합니다.
이미 서버 설치 때 사용하던 터미널이라면 같은 저장소 루트에서 이어서 실행합니다.

```bash
read -r -p '저장소 절대 경로: ' KEYCLOAK_REPO_DIR
cd "$KEYCLOAK_REPO_DIR"
pwd
ls Makefile deploy/keycloak/scripts/setup_discovery.py
python3 --version
bash --version
kubectl version --client
make --version
```

`cd`나 도구 확인이 실패하면 다음 명령을 진행하지 말고 경로·설치를 먼저 확인합니다.
이 문서의 명령은 같은 터미널에서 순서대로 실행합니다. 새 터미널을 열면 아래 context 선택부터 다시 실행합니다.

### 3-2. 현재 context 확인과 작업 대상 선택

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p '설정할 Kubernetes context 이름: ' KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get secret keycloak-runtime
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=5m
```

목록의 `NAME` 값을 입력합니다. 현재 context가 대상이면 첫 명령이 출력한 이름을 그대로 입력합니다.
빈 값을 입력하거나 다른 클러스터가 조회되면 context 선택을 다시 합니다.
이후 명령은 선택한 context를 명시하며 `kubectl config use-context`로 전역 설정을 바꾸지 않습니다.
Secret 조회는 존재 여부 확인이며 관리자 비밀번호의 유효성은 Job 실행 시 확인합니다.

### 3-3. 사내 IdP 입력 파일 편집

1번 IdP를 신규 설정하거나 갱신할 때만 필요합니다. 이미 provider가 정상이고 2·3번만 실행한다면 생략합니다.

```bash
chmod 600 deploy/keycloak/env/prod.env
vi deploy/keycloak/env/prod.env
```

`vi`에서 `i`로 편집을 시작해 위 2절의 `CORP_OIDC_CLIENT_ID`, `CORP_OIDC_CLIENT_SECRET`을 입력하고,
`Esc` → `:wq` → Enter로 저장합니다. 다른 편집기를 사용해도 됩니다.
기존 서버·DB·관리자 항목은 유지합니다. 파일을 `source`로 실행하지 않습니다.
이 단계에는 Portal client ID·secret이나 Portal env 파일이 필요하지 않습니다.

## 4. 기본 사용: IdP만 설정

위 3절에서 실행 위치·context·입력을 준비한 뒤 아래를 실행합니다.
이미 Realm과 provider가 정상 동작한다면 **4-1절로 이동**합니다.

먼저 입력·Discovery를 검사합니다. 다음 명령은 설정을 적용하지 않습니다.

```bash
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$KEYCLOAK_KUBE_CONTEXT" --env deploy/keycloak/env/prod.env
```

검사가 통과하면 IdP를 적용합니다.

```bash
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-oidc-setup
```

Make 명령은 Secret·관리 ConfigMap을 준비하고 IdP Job을 재생성한 뒤 최대 15분 완료를 기다립니다.
직접 `kubectl delete job`이나 `kubectl apply`를 추가 실행할 필요는 없습니다.
Admin Console에서 `etch` realm → `Identity providers → oidc`를 확인합니다.

다른 env를 사용한다면 검사 명령의 `--env`와 적용 명령의 `KEYCLOAK_ENV`에 같은 경로를 지정합니다.

```bash
read -r -p '사내 IdP env 절대 경로: ' KEYCLOAK_ENV_PATH
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$KEYCLOAK_KUBE_CONTEXT" --env "$KEYCLOAK_ENV_PATH"
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
```

### 4-1. provider가 정상일 때: User Profile → IdP mapper

현재처럼 provider 생성과 로그인이 완료됐다면 다음 두 단계를 각각 실행합니다.
먼저 User Profile을 등록합니다. 기존 프로필 정의는 프로젝트 정의로 교체되므로 별도 커스텀 정의가 있다면 먼저 검토합니다.

```bash
make keycloak-profile-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-user-profile-setup
```

기존 사용자에 `knox_id`, `department`, `grd_name` 값이 있다면 이 시점에
[저장 이름 전환](06_CLAIMS.md#기존-사용자-저장-이름-전환)을 실행합니다. 신규 사용자만 있는 경우에는 생략합니다.
그다음 IdP mapper를 설정합니다. `Realm settings`의 `Email as username`은 꺼져 있어야 합니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-idp-mappers-setup
```

`Realm settings → User profile`에서 `loginid`, `deptname`, `grdName` 등을,
`Identity providers → oidc → Mappers`에서 수신 mapper를 확인합니다.
시험 계정으로 기존에 사용한 사내 로그인 경로를 다시 거친 후 `Users`에서 실제 저장값을 확인합니다.
Keycloak 세션만 재사용하면 사내 정보가 새로 수신되지 않을 수 있습니다.

**여기까지 진행하고 Portal 연결은 나중에 해도 됩니다.** 2·3번은 Portal env나 client를 요구하지 않습니다.
Portal의 토큰 발급·앱 로그인 검증은 4번을 적용하고 Portal API 설정까지 준비한 뒤 수행합니다.

### 4-2. 나중에 Portal을 연결할 때

새 터미널이라면 위 3-1·3-2절의 저장소 이동·context 선택을 다시 합니다.
[Portal 입력 안내](env/02_ENVIRONMENT.md#portal-앱용-값)에 따라 전용 client 정보를 준비하고 다음을 실행합니다.

```bash
vi deploy/portal/env/prod/api.env
make keycloak-portal-client-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/portal-keycloak-client
```

이 명령은 Portal client·token mapper를 설정하며 사내 IdP·프로필·수신 mapper를 다시 설정하지 않습니다.
Portal API Secret·배포는 별도이므로 [Portal 연결 절차](../portal/k8s/jobs/keycloak-client/README.md)를 이어서 진행합니다.

## 5. 선택 사용: 기존 통합 명령

위 3절의 준비를 마친 뒤 **1~3번을 연속 적용하려는 경우에만** 사용합니다.
현재처럼 provider가 정상일 때는 4-1절의 단계별 실행을 사용하면 됩니다.
기존 저장 이름 전환이 필요하면 프로필과 mapper 사이에 값 복사가 필요하므로 단계별로 실행합니다.
아래는 `KEYCLOAK_PORTAL_ENV=`를 명시해 Portal 연결을 제외합니다.

```bash
make keycloak-oidc-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV=
make keycloak-oidc-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV=
```

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-oidc-check` | Discovery·입력·필요 파일 검사. 클러스터 로그인 성공까지 검증하지 않음 |
| `keycloak-oidc-setup` | OIDC Secret → 관리 ConfigMap → IdP → User Profile·IdP mapper |
| 위 명령에 `KEYCLOAK_PORTAL_ENV` 추가 | 지정한 Portal env로 4번 client·token mapper도 이어서 처리 |

```bash
make keycloak-oidc-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
make keycloak-oidc-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
```

통합 명령은 0번 Realm 생성과 5번 SDWT 설정, Portal API 배포를 수행하지 않습니다.
같은 작업을 단계별 명령으로 이미 완료했다면 통합 명령을 반복할 필요는 없습니다.

## 6. 완료와 실패 확인

IdP는 `Identity providers → oidc`, 사용자 정보는 사내 재로그인 후 `Users`에서 확인합니다.
실제 claim 발급은 discovery의 `claims_supported` 목록만으로 보장되지 않습니다.
매핑 규칙은 [06_CLAIMS.md](06_CLAIMS.md), 각 Job 이름과 재실행 명령은 [단계별 설정](04_SETUP_FLOW.md)에 있습니다.

통합 실행은 앞 Job 완료 후 다음 Job으로 넘어갑니다. 실패 전 적용된 설정은 유지하며 자동 롤백하지 않습니다.
원인을 수정한 뒤 필요한 단계만 다시 실행할 수 있습니다. 동일 환경에서 여러 설정 명령을 동시에 실행하지 마세요.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get pods
read -r -p '확인할 Job 이름: ' KEYCLOAK_JOB_NAME
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso describe job "$KEYCLOAK_JOB_NAME"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs "job/$KEYCLOAK_JOB_NAME"
```

IdP는 `keycloak-oidc-setup`, 프로필은 `keycloak-user-profile-setup`,
수신 mapper는 `keycloak-idp-mappers-setup`, 통합 claim Job은 `keycloak-oidc-claim-mappers`입니다.
실행하지 않은 단계의 Job이 없는 것은 정상입니다. 실패 원인을 수정한 후 해당 Make 명령을 다시 실행하면 Job이 재생성됩니다.

참고: [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker), [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).
