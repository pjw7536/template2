# Account 모듈

[모듈 목록](README.md) · [문서 홈](../README.md) · [API 호출 계약](../api/02-account.md)

Account는 사용자 식별 정보와 Keycloak 로그인 세션의 소속·권한 조회를 제공합니다.
앱 역할과 SDWT 등급은 Keycloak에서 관리하며 Portal의 기존 소속 변경·권한 승인 기능은 종료됐습니다.

권한은 두 단계로 이해하면 됩니다. **앱 역할**은 메일·대시보드 같은 기능에 들어갈 수 있는지를,
**SDWT 등급**은 해당 업무 데이터에서 조회·쓰기·삭제 중 무엇을 할 수 있는지를 정합니다.
앱에 들어갈 수 있어도 데이터 범위가 없으면 원하는 자료를 볼 수 없습니다.
아래에서 역할 이름과 그룹 형식, Portal 화면에서 확인할 정보를 차례로 설명합니다.

## 권한 원천

- 앱 역할은 검증된 토큰의 `resource_access[OIDC_CLIENT_ID].roles`에서 읽습니다.
- `portal-admin`은 전체 앱 관리자이며 전체 SDWT 범위를 허용합니다.
- `portal-all-apps`는 전체 앱 사용 역할입니다. SDWT 데이터 권한은 별도로 필요합니다.
- `<scope>-user`는 해당 앱 사용을 허용합니다.
- `<scope>-admin`은 `access-stats`, `appstore`, `emails`, `l3-spider`, `line-dashboard`, `voc`에서 지원합니다.
- 활성 앱의 유효 역할 또는 전체 앱 역할이 있어야 Portal 접근이 허용됩니다. 비활성 scope는 거부합니다.
- `deptid`와 부서 이름만으로 앱 권한을 부여하지 않습니다.
- Django `is_staff`/`is_superuser`와 DB의 기존 권한 행은 로그인 권한을 대신하지 않습니다.

## SDWT 데이터 범위

토큰의 `groups`는 `/<SDWT>/<등급>` 형식을 사용합니다.

| 등급 | 권한 |
| --- | --- |
| `viewer` | 조회 |
| `user` | 조회·쓰기 |
| `admin` | 조회·쓰기·삭제 |

동일 SDWT의 여러 등급은 가장 높은 등급을 사용합니다. 앱 접근과 SDWT 데이터 범위는 별도로 검사합니다.
현재 소속만으로 그룹 권한을 자동 부여하지 않습니다. `portal-admin`은 전체 범위를 사용합니다.

## 세션과 데이터

검증된 권한은 서버 세션의 `portal_authorization`에 저장하고 요청 사용자에 연결합니다.
역할·그룹 변경 후 재로그인이 필요합니다. `User`에는 EPID 등 신원을 저장하며,
기존 `Affiliation`, `UserAccess`, `UserSdwtProdAccess`, `AccessPolicyRule`,
`UserScopeAffiliationGrant` 등은 DB 이력으로 남아 있어도 현재 로그인 권한의 원천은 아닙니다.
`AccessScope`는 활성 앱 카탈로그로 사용합니다.

## 화면과 API

`/settings/account`와 `/settings/permissions`는 현재 계정 정보와 Keycloak 관리 안내를 제공합니다.
`/settings/members`는 Portal 관리자에게 사용자 목록을 최대 500명까지 표시합니다.
`/api/v1/account/overview`와 `/api/v1/auth/me`에서 현재 세션 권한을 확인합니다.
종료된 소속 변경·권한 관리·외부 소속 동기화 view는 `410 managed_by_keycloak`을 반환합니다.
일부 경로는 공통 middleware의 접근·신원 검사에서 먼저 차단될 수 있습니다.
[Account API](../api/02-account.md)에 현재 조회와 종료 경로를 구분했습니다.

## 운영 확인

접근 오류는 Keycloak Portal client 역할, SDWT 그룹, 활성 scope와 재로그인 여부를 확인합니다.
DB 권한 테이블을 수정해 접근을 복구하지 않습니다. 서버 설정은 [Keycloak 문서](../../deploy/keycloak/README.md)를 따릅니다.

## 관련 코드

- `apps/portal/api/api/account/urls.py`
- `apps/portal/api/api/account/views/keycloak.py`
- `apps/portal/api/api/account/services/keycloak_access.py`
- `apps/portal/api/api/auth/services/authentication.py`
- `apps/portal/web/src/features/account`
