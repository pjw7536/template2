# Account API

현재 로그인 세션의 소속·앱 역할·SDWT 등급과 사용자 검색을 제공합니다.
권한 변경은 Keycloak에서 수행합니다.

## 현재 조회 API

| Method | Path | 응답 |
| --- | --- | --- |
| GET | `/api/v1/account/overview` | 현재 세션 계정·권한 |
| GET | `/api/v1/account/access/users` | `overview`와 동일한 현재 세션 정보 |
| GET | `/api/v1/account/access/matrix` | `overview`와 동일한 현재 세션 정보 |
| GET | `/api/v1/account/line-sdwt-options` | 현재 세션의 line·접근 가능한 SDWT |
| GET | `/api/v1/account/users` | 사용자 검색 pool |

`overview`의 필드는 `authorizationSource`, `hasAllAppsAccess`, `isPortalAdmin`,
`department`, `userSdwtProd`, `line`, `sdwtAccess`, `scopeAccess`입니다.
`access/users`와 `access/matrix`는 전체 사용자 목록이나 편집 가능한 권한 표를 반환하지 않습니다.

`line-sdwt-options`는 `lines`, `userSdwtProds`를 반환합니다. 현재 소속이 접근 가능한 SDWT에
포함되고 line이 있을 때만 해당 line 항목을 제공합니다.

## 종료된 API

아래 경로의 view는 요청 방식·입력과 무관하게 HTTP 410, 오류 코드 `managed_by_keycloak`을 반환합니다.
공통 middleware의 Portal·신원 검사가 먼저 적용되는 경로는 이 단계에서 401/403으로 차단될 수 있습니다.
기존 payload를 보내도 DB 소속·권한을 변경하지 않습니다.

- `affiliation`, `affiliation/approve`, `affiliation/requests`, `affiliation/members`, `affiliation/access`, `affiliation/reconfirm`
- `access/request`, `access/pending-requests`, `access/pending-requests/bulk-approve`
- `access/users/<user_id>/decision`, `access/users/<user_id>/data-scope`, `access/users/<user_id>/apply-all`
- `access/policy-rules`, `access/policy-rules/bulk-apply`, `access/policy-rules/<rule_id>`
- `access/audit-logs`, `external-affiliations/sync`

위 상대 경로의 prefix는 `/api/v1/account/`입니다. 외부 소속 동기화도 종료됐으므로 Airflow Bearer token으로 재활성화되지 않습니다.

## 사용자 검색

```http
GET /api/v1/account/users?search=kim&contactField=email
```

| Query | 설명 |
| --- | --- |
| `search` | 사용자 검색어 |
| `department` | 부서 필터 |
| `userSdwtProd` | 소속 필터 |
| `contactField` | `email` 또는 `knox_id` |
| `limit` | 1~500 정수, `userSdwtProd`와 함께일 때만 `all` |
| `includeExternalSnapshots` | 미가입 외부 스냅샷 포함 여부 |

조회별 인증·입력 검사는 실제 view와 serializer를 따릅니다. 권한의 원천과 역할은
[Account 모듈](../modules/account.md), 세션 응답은 [Auth API](auth.md)를 봅니다.
