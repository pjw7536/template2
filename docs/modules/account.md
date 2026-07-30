# Account 모듈

Account는 이 앱의 권한 기준이 되는 소속과 접근 권한을 관리합니다.

## 기능 요약

- 현재 사용자 소속 조회
- 소속 변경 요청/승인/거절
- 외부 예측 소속 동기화와 재확인
- `user_sdwt_prod` 접근 권한 부여/회수
- Portal·앱·기능 접근 권한 통합 매트릭스 관리
- 소속 기반 앱의 앱별 데이터 범위 관리
- 소속별 멤버 조회
- 사용자 검색 pool 제공

## 왜 중요한가

`user_sdwt_prod`는 단순한 사용자 정보가 아니라 접근 권한의 기준입니다.

- Emails는 접근 가능한 소속 메일함만 보여줍니다.
- Assistant는 접근 가능한 소속만 RAG 검색 범위에 넣습니다.
- Drone은 대상 소속을 기준으로 알림 수신자를 정합니다.

## 핵심 데이터

| 모델 | 의미 |
| --- | --- |
| `User` | 사용자 기본 정보와 현재 소속 |
| `Affiliation` | 선택 가능한 부서/라인/user_sdwt_prod 조합 |
| `UserSdwtProdAccess` | 소속 멤버십 운영 role과 capability |
| `UserSdwtProdChange` | 소속 변경 요청 이력 |
| `ExternalAffiliationSnapshot` | 외부 시스템이 예측한 소속 |
| `AccessScope` | Portal·앱·기능별 접근 권한과 데이터 범위 정책 |
| `AccessPolicyRule` | scope별 부서 자동 접근 정책 |
| `UserAccess` | 사용자별 scope 승인 상태, `user`/`admin` 역할, 명시적 전체 데이터 범위 |
| `UserScopeAffiliationGrant` | 사용자·앱·소속별 추가 데이터 범위 grant |
| `AccessAuditLog` | 접근 상태·정책·scope 변경 감사 이력 |

## 소속 접근 role

| Role | 의미 |
| --- | --- |
| `viewer` | 소속 데이터 조회 |
| `member` | 조회 + 일반 변경 작업 |
| `manager` | 조회 + 일반 변경 + 삭제 + 소속 변경 승인 + 권한 관리 |

staff/superuser는 활성 소속의 기존 데이터 접근 제한을 대부분 우회합니다. 비활성 또는
존재하지 않는 소속은 우회할 수 없습니다. 이 규칙은
`UserSdwtProdAccess`에만 적용되며 Portal·앱의 `admin` 역할 판정에는 사용하지 않습니다.

## 앱별 소속 데이터 범위

앱 사용 가능 여부와 앱에서 볼 수 있는 소속 데이터는 서로 다른 권한입니다.

- `AccessScope.data_scope_type=none`인 앱은 앱 접근만 허용되면 사용할 수 있습니다.
- `data_scope_type=affiliation`인 앱은 앱 접근 판정 후 소속 데이터 범위를 추가로 계산합니다.
- 현재 소속 자동 포함 여부는 `AccessScope.include_current_affiliation`에 고정합니다.
- 추가 소속은 `UserScopeAffiliationGrant(user, scope, affiliation)`로 앱마다 따로 부여합니다.
- 활성·미만료 자동 grant는 수동 변경에서 보호하고, 효력이 끝난 자동 grant는 관리자 선택 시 감사 로그를 남기며 수동 grant로 전환합니다.
- 선택 소속 추가·회수와 `UserAccess.data_scope_mode` 변경은 모두 변경 사유가 필요합니다.
- `UserAccess.data_scope_mode=all`은 활성 소속 전체를 뜻하며 명시적인 앱 허용 행이 필요합니다.
- 앱 `admin` 역할만으로 `all`이 되지 않습니다. 역할은 기능 권한이고 데이터 범위는 조회 경계입니다.
- Emails의 미분류 데이터와 전역 운영 특권은 `admin` 역할과 `all` 범위를 모두 가진 경우에만 허용합니다.
- 앱 접근이 거부되거나 scope가 비활성화되면 남아 있는 소속 grant도 효력이 없습니다.
- `Affiliation.is_active=false`는 현재 소속·소속 역할·앱별 grant를 모두 일시 중지하는
  전역 기준입니다. 연결 설정은 보존되고 superuser Admin action만 활성 상태를 바꾸며
  변경은 감사 로그에 기록됩니다.
- `all`에서 `default`로 돌아가는 접근 차단·정책 초기화·일괄 변경도 `data_scope_change` 감사 이력에 남습니다.

현재 소속 기반 범위를 사용하는 시스템 앱은 Emails와 Assistant입니다. 그 외 시스템 앱은
`none`이며 소속 grant를 만들 수 없습니다. 실효 범위 계산은
`services/data_scope.py`의 중앙 resolver만 사용합니다.

## Portal·scope 접근 계층

- Portal 접근이 허용되어야 앱·기능 접근 판정도 최종 허용될 수 있습니다.
- Portal이 차단되면 개별 하위 scope가 수동 또는 자동 허용 상태여도 최종 접근은 차단됩니다.
- 차단 전 하위 판정은 API의 `underlyingAccess`에 보존되므로 Portal 복구 후 기존 설정이 다시 적용됩니다.
- Portal과 모든 하위 scope의 접근 역할은 `user`와 `admin` 두 개뿐입니다.
- Portal `admin`은 전체 접근 권한을 관리하고, 앱 `admin`은 해당 앱의 관리자 기능만 사용합니다.
- 자동 정책과 일괄 승인은 `user`만 부여하며 `admin`은 사용자별로 명시해야 합니다.
- `GET /api/v1/auth/me`는 Portal과 모든 활성 scope를 `scope_access` 하나로 반환합니다.
- 접근 신청은 `/access/request`의 `scopes` 배열, 관리 결정은 `/access/users/<user_id>/decision`만 사용합니다.
- 여러 scope 신청과 필요한 Portal 신청은 하나의 transaction으로 저장됩니다.
- 앱 관리자 판정은 해당 앱의 `UserAccess=allowed/admin`만 사용하며 `is_staff`를 사용하지 않습니다.
- superuser만 최초 Portal admin 지정과 비상 운영을 위해 전체 제한을 우회합니다.

## 소속 변경 흐름

1. 사용자가 새 `user_sdwt_prod`를 제출합니다.
2. 서버가 `Affiliation`에 존재하는 값인지 확인합니다.
3. 기존 대기 요청이 있으면 이전 요청을 `SUPERSEDED`로 바꿉니다.
4. 예측 소속과 같으면 자동 적용합니다.
5. 승인이 필요하면 `PENDING` 요청으로 저장합니다.
6. 대상 소속의 `manager`가 승인하면 사용자 소속이 갱신됩니다.
7. 요청자는 자신의 소속 변경 요청을 승인하거나 거절할 수 없습니다.

사용자별 `PENDING` 요청은 DB에서 한 건으로 제한합니다. 생성은 사용자 잠금으로
직렬화하고, 승인·거절은 대상 소속과 사용자를 잠근 뒤 현재 유효한 요청인지와 처리자의
최신 `manager` 역할을 다시 확인합니다. 따라서 동시에 재신청하거나 manager 역할이
회수되어도 오래 읽은 상태로 요청을 처리하지 않습니다.

## 외부 예측 소속 재확인

1. Airflow가 외부 예측 소속을 동기화합니다.
2. 예측값이 현재 소속과 달라지면 재확인 플래그가 켜집니다.
3. 사용자는 예측값을 수락하거나 다른 소속을 선택합니다.
4. 다른 소속을 선택하면 승인 대기로 갈 수 있습니다.

## 대표 시나리오

| 상황 | 결과 |
| --- | --- |
| 신규 사용자에게 유효한 예측 소속이 있음 | 자동 적용 가능 |
| 예측 소속이 없거나 유효하지 않음 | 온보딩에서 직접 선택 |
| 예측값과 같은 소속 선택 | 자동 적용 가능 |
| 승인자가 있고 예측값과 다른 소속 선택 | 승인 대기 |
| 승인 대기 중 재요청 | 이전 요청은 `SUPERSEDED` |
| 마지막 manager 회수 시도 | 거부 |

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/settings/account`, `/settings/members`, `/settings/permissions` |
| Frontend | `apps/web/src/features/account`, `apps/web/src/features/auth` |
| Backend API | `/api/v1/account/**`, `/api/v1/auth/me` |
| 데이터 | `User`, `Affiliation`, `UserCurrentAffiliation`, `UserSdwtProdAccess`, `UserScopeAffiliationGrant`, `UserSdwtProdChange`, `ExternalAffiliationSnapshot`, `AccessScope`, `AccessPolicyRule`, `UserAccess`, `AccessAuditLog` |
| 외부/배치 | Airflow `external-affiliations/sync` |

## 운영 포인트

- 소속이 예상과 다르면 `ExternalAffiliationSnapshot`과 `UserCurrentAffiliation`을 함께 확인합니다.
- 소속 권한 문제는 `UserSdwtProdAccess` role을, Portal·앱·기능 권한 문제는 `UserAccess`, `AccessPolicyRule`, Portal 최종 판정을 함께 확인합니다.
- Emails·Assistant 데이터 누락은 앱 `UserAccess`, `data_scope_mode`, 현재 소속, 해당 앱의 `UserScopeAffiliationGrant`를 함께 확인합니다.
- 권한 관리 화면 접근 문제는 해당 사용자의 Portal `UserAccess`가 `allowed/admin`인지 확인합니다.
- `UserAccess`와 `AccessPolicyRule`은 Portal 권한 관리 화면/API에서만 변경하며 Django Admin에서는 읽기 전용입니다.
- `UserSdwtProdAccess`도 마지막 manager 불변조건을 보장하기 위해 Members 화면/API에서만 변경하며 Django Admin에서는 읽기 전용입니다.
- 소속 역할 부여·변경·회수는 대상 소속 잠금 안에서 최신 manager 권한을 재검사하고 `affiliation_role_grant`, `affiliation_role_change`, `affiliation_role_revoke` 감사 이력을 남깁니다.
- 소속 기준정보 생성·자동 동기화 변경은 각각 `affiliation_create`, `affiliation_update` 감사 이력을 남깁니다. 활성·비활성 일괄 변경은 Admin에서 사유를 입력하고 선택 행 전체를 하나의 transaction으로 처리합니다.
- 소속 변경 승인으로 새 소속 역할이 생성·승격되거나 이전 소속 역할이 강등되는 경우도 승인자와 변경 사유를 같은 감사 이력에 남깁니다.
- 런타임 접근 판정과 request-scoped resolver는 읽기 전용 `access_runtime.py`에 있고,
  접근 신청·관리 결정·정책·감사 쓰기는 `access_control.py`에 있습니다.
- `AccessScope`는 migration으로만 추가하고 `key`·유형은 생성 후 변경하지 않습니다.
- 최초 권한 관리자는 지정한 Django superuser가 명시적으로 부여하며 모든 변경 내역은 `AccessAuditLog`에 남습니다.
- scope와 사용자는 물리 삭제하지 않고 `is_active=false`로 비활성화해 감사 참조를 보존합니다.
- Admin에서는 scope의 표시 이름·활성 상태·요청 가능 여부만 변경하며 같은 canonical 감사 로그에 남깁니다.
- 외부 동기화 실패는 Airflow Bearer token과 `docs/configuration.md`의 auth/env 설정을 확인합니다.

## 관련 API

- `docs/api/account.md`

## 관련 코드

- `apps/api/api/account/views.py`
- `apps/api/api/account/models.py`
- `apps/api/api/account/selectors.py`
- `apps/api/api/account/serializers.py`
- `apps/api/api/account/services/access_control.py`
- `apps/api/api/account/services/access_runtime.py`
- `apps/api/api/account/services/data_scope.py`
- `apps/api/api/account/services/affiliation_requests.py`
- `apps/api/api/account/services/affiliations.py`
- `apps/api/api/account/services/external_sync.py`
- `apps/api/api/account/services/overview.py`
- `apps/api/api/account/services/users.py`
- `apps/web/src/features/account`
- `apps/web/src/features/account/pages/PermissionsPage.jsx`
- `apps/web/src/features/account/components/*Permission*.jsx`
- `apps/web/src/features/auth`
