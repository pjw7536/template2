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

## 4. 기본 사용: IdP만 설정

```bash
read -r -p '설정할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

이 명령은 1번 IdP만 설정합니다. 다음은 [2번 User Profile](04_SETUP_FLOW.md#2-user-profile-등록)입니다.
다른 env를 사용하려면 `KEYCLOAK_ENV=/절대/경로/keycloak.env`를 지정합니다.

## 5. 선택 사용: 기존 통합 명령

아래는 1~3번을 연속 적용하려는 경우에만 사용합니다.

```bash
make keycloak-oidc-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-oidc-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
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

참고: [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker), [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).
