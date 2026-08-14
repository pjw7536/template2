# Auth API

Auth API는 Keycloak OIDC 로그인과 Django session 관리를 담당합니다. 사내 OIDC는 Keycloak의 upstream identity provider이며 Portal은 사내 OIDC token을 직접 신뢰하지 않습니다.

## 호출자

- 브라우저 SPA
- OIDC provider callback

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/auth/config` | 공개 | 프론트 인증 설정 조회 |
| GET | `/api/v1/auth/login` | 공개 | OIDC 로그인 시작 |
| GET, POST | `/auth/keycloak/callback/` | OIDC code flow | Keycloak callback 처리 |
| GET | `/api/v1/auth/me` | Session | 현재 사용자 조회 |
| GET | `/api/v1/auth/logout` | Session | Grist 세션 종료 후 IdP logout redirect |
| POST | `/api/v1/auth/logout` | Session | 첫 로그아웃 경유 URL JSON 반환 |
| GET | `/api/v1/auth/` | 공개 | 프론트 redirect 보조 |

## 로그인 시작

```http
GET /api/v1/auth/login?target=/account
```

동작:

1. OIDC 설정 여부를 확인합니다.
2. `target` 또는 `next`를 state로 인코딩합니다.
3. nonce를 세션에 저장합니다.
4. PKCE S256 verifier를 session에 저장하고 Keycloak authorize URL로 redirect합니다.

## Callback

```http
GET /auth/keycloak/callback/?code=<authorization-code>&state=<state>
```

Keycloak이 `code`, `state`를 query로 전달합니다. POST callback도 같은 두 필드에 한해 호환합니다.

동작:

1. state와 redirect target을 검증합니다.
2. 일회용 code와 PKCE verifier를 token set으로 교환합니다.
3. JWKS로 ID/access token의 서명, issuer, audience, 만료와 nonce를 검증합니다.
4. `/affiliations/<소속>/<viewer|member|manager>`가 정확히 하나이고 `portal-user` 또는 `portal-admin` 역할이 있는지 확인합니다.
5. claim snapshot으로 shadow `account.User`를 생성하거나 갱신하고 Django session login 후 target으로 redirect합니다.

## 현재 사용자

```http
GET /api/v1/auth/me
```

응답에는 사용자 기본 정보, 표시용 소속 snapshot, Keycloak group과 realm/client role이 포함됩니다. access token은 5분이며 만료 30초 전 refresh합니다. refresh된 access token은 다시 검증해 shadow User의 역할 snapshot을 갱신하므로 회수된 역할을 이전 Django session이 계속 보유하지 않습니다.

```json
{
  "isAuthenticated": true,
  "user": {
    "id": 1,
    "username": "user",
    "knoxId": "knox.user",
    "userSdwtProd": "G-A",
    "groups": ["/affiliations/G-A/member"],
    "clientRoles": {"portal": ["portal-user", "work-hub-user"]}
  }
}
```

## 로그아웃

Work Hub가 활성화되어 있거나 `GRIST_LOGOUT_ENABLED=1`인 세션 정리 기간에는 첫 로그아웃 요청이 Grist `/logout`을 반환합니다. Grist가 자체 session을 제거한 뒤 `grist_cleared=1` marker로 돌아오면 Portal은 기존 IdP logout URL로 이동합니다. 두 플래그가 모두 꺼져 있거나 Grist public URL이 안전하지 않으면 기존 IdP logout으로 바로 진행합니다.

## 오류

| Status | 상황 |
| --- | --- |
| 400 | callback 값 누락 또는 state 오류 |
| 401 | 로그인되지 않았거나 Keycloak refresh/session 검증이 실패한 상태에서 `/me` 호출 |
| 403 | 허용되지 않은 redirect target |
| 503 | Keycloak OIDC provider 설정 누락 |

## 관련 모듈 문서

- `docs/modules/auth.md`
