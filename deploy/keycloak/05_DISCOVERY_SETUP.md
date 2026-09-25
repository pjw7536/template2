# 05. 사내 OIDC Discovery 참고

[전체 설치 순서](README.md) · 실행 명령: [Keycloak 자체 설정](04_SETUP_FLOW.md#2-사내-identity-provider-생성)

Discovery는 사내 IdP의 접속 정보를 자동으로 가져오는 기능입니다.
이 문서는 입력의 의미만 설명합니다. 실행 위치·context 선택·검사·적용은 위 실행 안내에서 한 번만 진행합니다.

## 자동으로 가져오는 값

실행 호스트가 `CORP_OIDC_DISCOVERY_URL`의 JSON을 조회하고 아래 정보를 IdP Job에 전달합니다.

| Metadata 항목 | 사용 목적 | 필수 여부 |
| --- | --- | --- |
| `authorization_endpoint` | 브라우저의 사내 인증 주소 | 필수 |
| `token_endpoint` | 인증 코드를 토큰으로 교환 | 필수 |
| `issuer` | 토큰 발급자 검증 | 필수 |
| `jwks_uri` | 서명 검증용 공개키 | 필수 |
| `userinfo_endpoint` | 사용자 정보 추가 조회 | 제공 시 사용 |
| `end_session_endpoint` | 사내 로그아웃 | 제공 시 사용 |

필수 값이 없으면 검사가 중단됩니다. 신규 IdP에 제공되지 않은 선택 URL은 추정해서 만들지 않습니다.
endpoint는 HTTPS를 사용하고 서명 검증은 활성화합니다. issuer는 받은 값을 그대로 사용합니다.
해석 결과는 임시 env와 Kubernetes Secret으로 전달하며 원본 `prod.env`를 덮어쓰지 않습니다.

## 별도로 준비하는 값

사내 client ID·secret은 AD FS에서 발급받아 [환경변수 안내](env/02_ENVIRONMENT.md#사내-identity-provider용-값)에 따라 입력합니다.
Discovery는 credential·사용자 claim 값·접근 권한을 발급하지 않습니다.
인증 방식 `client_secret_post`는 `Client secret sent in the request body`에 해당합니다.
metadata에 인증 방식 목록이 없으면 도구는 `client_secret_basic`을 기본 지원 방식으로 검사하므로 실제 client의 지원 방식을 확인합니다.

## 네트워크와 인증서

- 실행 호스트: Discovery URL에 접근하고 CA를 신뢰해야 합니다. 별도 CA 파일은 `SSL_CERT_FILE`로 지정합니다.
- Keycloak Pod: 사내 Token·JWKS·UserInfo endpoint에 접근하고 CA를 신뢰해야 합니다.
- 브라우저: 사내 인증 주소와 공개 Keycloak 주소에 접근할 수 있어야 합니다.

호스트의 CA 신뢰가 Pod에 자동 전달되지는 않습니다. [TLS 준비](03_TLS.md)를 참고합니다.

참고: [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).
