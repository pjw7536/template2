# Account API

Account는 Keycloak claim을 보관하는 shadow `User`와 읽기 전용 계정 화면을 제공합니다. 소속 신청·승인, 추가 소속 grant, 자동 정책, 감사 이력의 쓰기 API는 Keycloak 전환 후 제공하지 않습니다.

## 호출자와 인증

- 브라우저 SPA와 내부 업무 모듈이 호출합니다.
- 모든 endpoint에 Keycloak 로그인으로 만든 Django session이 필요합니다.
- 권한 원본은 Keycloak group/client role이며 Django superuser는 우회 권한이 아닙니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/account/users` | 활성 shadow 사용자 검색 |
| GET | `/api/v1/account/line-sdwt-options` | 기존 업무 화면 호환용 line/소속 옵션 조회 |

그 밖의 기존 Account 쓰기 경로는 라우팅하지 않습니다. `/settings/account`는 `/api/v1/auth/me`의 내 정보, 표시용 기본 소속과 Keycloak 역할을 읽기 전용으로 보여줍니다. `/settings/members`, `/settings/permissions`와 Django Account 관리 화면은 제거됩니다.

## Keycloak 권한 계약

- 기본 소속 group은 `/affiliations/<소속>/<viewer|member|manager>` 형식이며 사용자마다 정확히 하나입니다.
- Portal client role은 `portal-user/admin`과 `<scope>-user/admin` 형식입니다.
- 일반 app user는 shadow User의 기본 소속 snapshot에 해당하는 데이터만 조회합니다.
- app admin은 해당 앱의 전체 데이터를 조회합니다.
- access token refresh 뒤 최신 group/client role을 다시 검증해 shadow User에 저장합니다.

`GET /api/v1/auth/me`의 `scope_access`는 기존 업무 화면이 공통으로 사용하는 판정 형식을 유지합니다.

```json
{
  "user_sdwt_prod": "G-A",
  "groups": ["/affiliations/G-A/member"],
  "client_roles": {
    "portal": ["portal-user", "emails-user"]
  },
  "scope_access": {
    "portal": {"allowed": true, "role": "user"},
    "emails": {"allowed": true, "role": "user"}
  }
}
```

## Legacy 제거 순서

현재 유효한 기본 소속과 Portal·앱 user/admin만 `migrate_legacy_access_to_keycloak`로 이관합니다. pending, denied, 만료 grant, 추가 데이터 범위와 상세 감사 이력은 이관하지 않습니다. 실제 cutover의 backup, row count/checksum, realm export·복원 시험과 권한 비교가 완료될 때까지 legacy non-User 테이블은 rollback 증적으로 읽기 전용 보존합니다. 검증 완료 뒤 별도 irreversible migration으로 즉시 제거합니다.

상세 절차는 `docs/operations.md`의 Keycloak 권한 전환 절을 따릅니다.
