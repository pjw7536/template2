# Auth

Auth feature는 `사내 OIDC → Keycloak → Django session` 인증을 담당합니다. Portal은 Keycloak issuer와 JWKS만 신뢰하며 upstream 사내 OIDC token을 직접 처리하지 않습니다.

## 로그인 흐름

1. 브라우저가 `/api/v1/auth/login`을 호출합니다.
2. API가 nonce, state와 PKCE S256 verifier를 Django session에 저장합니다.
3. 브라우저가 Keycloak authorize endpoint로 이동합니다.
4. Keycloak은 필요하면 사내 OIDC identity provider로 인증을 위임합니다.
5. `/auth/keycloak/callback/`이 authorization code를 token set으로 교환합니다.
6. JWKS로 서명, issuer, audience, 만료, nonce를 검증합니다.
7. `sabun`, 단일 affiliation group과 Portal client role을 검증해 shadow `account.User`를 갱신합니다.
8. Django session을 만든 뒤 안전한 frontend target으로 이동합니다.

access token 수명은 300초입니다. `/api/v1/auth/me`는 만료 30초 전에 refresh하고 최신 access token의 group/client role을 다시 shadow User에 저장합니다. refresh 또는 claim 검증이 실패하면 로컬 session을 종료하고 401을 반환합니다.

## 권한 입력

- 사용자마다 `/affiliations/<소속>/<viewer|member|manager>` group이 정확히 하나 필요합니다.
- `portal-user` 또는 `portal-admin`이 없으면 로그인하지 않습니다.
- 앱 역할은 `<scope>-user` 또는 `<scope>-admin`입니다.
- Django `is_superuser`는 권한 판정에서 사용하지 않습니다.

## 공개 표면

| 구분 | 경로 |
| --- | --- |
| Frontend | `/login` |
| Backend API | `/api/v1/auth/config`, `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/logout` |
| Callback | `/auth/keycloak/callback/` |

상세 endpoint와 오류 계약은 `docs/api/auth.md`, 환경 변수와 cutover 절차는 `docs/configuration.md`, `docs/operations.md`를 따릅니다.
