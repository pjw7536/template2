# Account API

Account API는 사용자 소속, 접근 권한, 사용자 검색을 제공합니다.

## 호출자

- 브라우저 SPA
- Airflow 또는 외부 배치
- Emails/Assistant 등 내부 모듈

## 인증

- 일반 API: Django session 필요
- 외부 소속 동기화: Airflow Bearer token 필요

## Endpoint

| Method | Path | Auth | 설명 |
| --- | --- | --- | --- |
| GET | `/api/v1/account/overview` | Session | 계정 화면 통합 정보 |
| GET | `/api/v1/account/affiliation` | Session | 내 소속/접근 가능 소속/선택 옵션 |
| POST | `/api/v1/account/affiliation` | Session | 소속 변경 요청 |
| GET | `/api/v1/account/affiliation/requests` | Session | 소속 변경 요청 목록 |
| POST | `/api/v1/account/affiliation/approve` | Session | 소속 변경 승인/거절 |
| GET | `/api/v1/account/affiliation/members` | Session | 소속 멤버 목록 |
| POST/DELETE | `/api/v1/account/affiliation/access` | Session + 소속 manager | 소속 접근 역할 부여·변경·회수 |
| GET/POST | `/api/v1/account/affiliation/reconfirm` | Session | 외부 예측 소속 재확인 |
| POST | `/api/v1/account/external-affiliations/sync` | Bearer token | 외부 예측 소속 동기화 |
| POST | `/api/v1/account/access/request` | Session | 내 Portal·앱·기능 scope 접근 신청 |
| GET | `/api/v1/account/access/users` | Session + Portal admin | scope별 사용자 접근 현황 |
| GET | `/api/v1/account/access/matrix` | Session + Portal admin | 사용자별 Portal·활성 하위 scope 권한 매트릭스 |
| POST | `/api/v1/account/access/users/<user_id>/decision` | Session + Portal admin | Portal·앱·기능 권한 승인/거절/부여/회수/역할 변경 |
| POST | `/api/v1/account/access/users/<user_id>/apply-all` | Session + Portal admin | 모든 관리 scope의 사용자 권한 일괄 변경 |
| GET/PUT | `/api/v1/account/access/users/<user_id>/data-scope` | Session + Portal admin | 소속 기반 앱의 사용자별 데이터 범위 조회/교체 |
| GET/POST | `/api/v1/account/access/policy-rules` | Session + Portal admin | scope별 부서 자동 허용 정책 조회/생성 |
| PATCH/DELETE | `/api/v1/account/access/policy-rules/<rule_id>` | Session + Portal admin | 자동 허용 정책 수정/삭제 |
| GET | `/api/v1/account/access/audit-logs` | Session + Portal admin | 접근 권한 감사 로그 |
| GET | `/api/v1/account/users` | Session | 사용자 검색 pool |
| GET | `/api/v1/account/line-sdwt-options` | Session | line/user_sdwt_prod 옵션 |

## 소속 변경 요청

```http
POST /api/v1/account/affiliation
Content-Type: application/json
```

```json
{
  "user_sdwt_prod": "G-A"
}
```

호환 키:

- `user_sdwt_prod`
- `userSdwtProd`

응답은 자동 적용 또는 승인 대기 상태를 반환합니다.

## 승인/거절

대상 소속의 `manager`만 처리할 수 있으며 요청자는 자신의 요청을 직접
승인하거나 거절할 수 없습니다.

```json
{
  "changeId": 123,
  "decision": "approve"
}
```

거절:

```json
{
  "changeId": 123,
  "decision": "reject",
  "rejectionReason": "소속 정보 불일치"
}
```

## 권한 부여/회수

부여 또는 역할 변경:

```http
POST /api/v1/account/affiliation/access
Content-Type: application/json
```

```json
{
  "userId": 55,
  "userSdwtProd": "G-A",
  "role": "manager",
  "reason": "G-A 운영 담당자 지정"
}
```

회수:

```http
DELETE /api/v1/account/affiliation/access
Content-Type: application/json
```

```json
{
  "userId": 55,
  "userSdwtProd": "G-A",
  "reason": "G-A 운영 업무 종료"
}
```

허용 role:

- `viewer`
- `member`
- `manager`

현재 소속 접근은 회수할 수 없으며, 마지막 `manager`는 강등하거나 회수할
수 없습니다. 부여·역할 변경·회수에는 500자 이하의 `reason`이 필수입니다.

부여·변경·회수는 대상 소속을 잠근 뒤 요청자의 최신 `manager` 역할을 다시 확인합니다.
성공한 변경은 각각 `affiliation_role_grant`, `affiliation_role_change`,
`affiliation_role_revoke` 감사 로그로 기록되며 대상 사용자와 소속, 변경 전후 role이
포함됩니다.

## Portal·scope 권한 매트릭스

```http
GET /api/v1/account/access/matrix?page=1&pageSize=20&search=kim&department=Etch
```

응답의 `scopes`는 `portal`을 첫 항목으로 반환하고 뒤에 활성 앱·기능 scope를 이름순으로 반환합니다.
모든 scope의 접근 payload는 같은 형태이며, 최종 허용 상태인 `allowed`와 고정 역할인 `role`을 포함합니다.

접근 역할은 다음 두 개뿐입니다.

- `user`: 해당 scope의 일반 기능 사용
- `admin`: 해당 scope의 관리자 기능 사용

Portal `admin`은 전체 scope의 권한 현황, 결정, 자동 정책, 감사 로그를 관리합니다. 앱 `admin`은 해당 앱의 관리자 기능만 사용할 수 있습니다. `is_superuser`는 최초 관리자 지정과 비상 운영을 위한 전역 우회 권한입니다.

Portal 접근이 차단되면 모든 하위 scope의 최종 판정도 차단됩니다. 이때 하위 scope payload는 `allowed=false`, `effectiveStatus=denied`, `source=portal_access_required`, `blockedByPortal=true`를 반환합니다. 기존 하위 판정은 변경하지 않고 `underlyingAccess`에 다음 형태로 보존합니다.

```json
{
  "allowed": false,
  "effectiveStatus": "denied",
  "source": "portal_access_required",
  "blockedByPortal": true,
  "underlyingAccess": {
    "allowed": true,
    "reason": "allowed",
    "effectiveStatus": "allowed",
    "source": "explicit_allowed"
  }
}
```

## 통일된 scope 접근 계약

`GET /api/v1/auth/me`는 권한 정보를 `scope_access` 하나로만 반환합니다. `portal_access`, `app_access` 필드는 없습니다.

```json
{
  "scope_access": {
    "portal": {
      "allowed": true,
      "scope": "portal",
      "role": "user"
    },
    "appstore": {
      "allowed": true,
      "scope": "appstore",
      "role": "admin",
      "blockedByPortal": false
    }
  }
}
```

사용자 신청은 scope 종류와 관계없이 한 API를 사용합니다.
요청 본문은 항상 `scopes` 배열이며, 앱을 신청하면 서버가 필요한 Portal 신청도 같은 transaction에서 함께 처리합니다. 하나라도 유효하지 않으면 어떤 신청도 저장하지 않습니다.

```http
POST /api/v1/account/access/request
Content-Type: application/json
```

```json
{
  "scopes": ["appstore", "voc"]
}
```

응답의 `accesses`는 실제 처리한 scope별 결과를 반환합니다.

```json
{
  "status": "pending",
  "accesses": {
    "portal": {
      "explicitStatus": "pending",
      "role": "user"
    },
    "appstore": {
      "explicitStatus": "pending",
      "role": "user"
    },
    "voc": {
      "explicitStatus": "pending",
      "role": "user"
    }
  }
}
```

관리자 결정도 사용자와 scope를 기준으로 한 API 하나만 사용합니다.

```http
POST /api/v1/account/access/users/55/decision
Content-Type: application/json
```

```json
{
  "scope": "appstore",
  "action": "grant",
  "role": "admin",
  "reason": "앱 운영 담당자"
}
```

대기 요청은 `approve` 또는 `reject`, 일반 수동 변경은 `grant`, `revoke`, `reset_to_policy`, `change_role`을 사용합니다. 일반 수동 변경에는 500자 이하의 `reason`이 필수입니다. `role`을 생략한 승인·부여는 항상 `user`가 됩니다. Portal 승인에서만 `approveAllApps: true`를 선택해 명시 차단되지 않은 활성 앱을 `user`로 함께 허용할 수 있습니다.

모든 관리 scope를 한 번에 변경할 때도 실제 운영 사유를 필수로 전달합니다.

```json
{
  "value": "admin",
  "reason": "서비스 운영 총괄 권한 부여"
}
```

잘못된 JSON body는 모든 접근 API에서 `{"error":"invalid_request","details":{...}}`, 잘못된 query는 `{"error":"invalid_query","details":{...}}` 형태로 반환합니다.

앱 관리자 기능은 모두 같은 기준을 사용합니다.

| Scope `admin` | 관리자 기능 |
| --- | --- |
| `appstore` | 다른 사용자의 앱·댓글 관리 |
| `l3-spider` | 개발자 옵션 조회 |
| `line-dashboard` | Drone target 기준 정보 관리 |
| `emails` | 전체·미분류 메일함 관리 |
| `access-stats` | 수동 통계 입력 (`admin` 전용) |
| `voc` | 다른 사용자의 게시글 관리 |

`is_staff`는 앱 관리자 판정에 사용하지 않습니다.
외부 통계 동기화는 예외적으로 `access-stats` 접근이 허용된 모든 로그인 사용자가 요청할 수 있고,
일반 사용자의 실제 외부 API 호출은 전역 기준 6시간에 한 번으로 제한됩니다.
`access-stats admin`과 슈퍼유저는 이 제한을 적용하지 않습니다.

## 앱별 소속 데이터 범위

`AccessScope.dataScopeType`은 앱이 소속 데이터 경계를 사용하는지 선언합니다.

- `none`: 앱 접근 권한만 판정하며 소속 범위는 적용하지 않음
- `affiliation`: 현재 소속과 앱별 명시 grant를 합쳐 데이터 범위를 판정

접근 payload의 `dataScopeMode`은 `default` 또는 `all`입니다. 앱 `admin`과 `all`은
독립적이며, 관리자가 앱 역할을 `admin`으로 바꾸어도 전체 소속 데이터는 자동으로 열리지
않습니다.

조회:

```http
GET /api/v1/account/access/users/55/data-scope?scope=emails
```

선택 범위 교체:

```http
PUT /api/v1/account/access/users/55/data-scope
Content-Type: application/json
```

```json
{
  "scope": "emails",
  "dataScopeMode": "default",
  "affiliationIds": [12, 18],
  "reason": "공동 운영 메일함"
}
```

선택 소속 추가·회수와 전체 활성 소속 범위 변경은 모두 사유를 반드시 남깁니다.

```json
{
  "scope": "emails",
  "dataScopeMode": "all",
  "affiliationIds": [],
  "reason": "메일 운영 총괄"
}
```

`all`은 대상 사용자의 해당 앱 `UserAccess`가 명시적으로 `allowed`일 때만 설정할 수
있습니다. `affiliationIds`는 활성 `Affiliation.id`만 허용합니다. `none` 앱, 비활성
scope, superuser 대상 변경은 거부합니다. 변경은 소속 단위
`data_scope_grant`, `data_scope_revoke`, `data_scope_change` 감사 로그로 기록됩니다.
접근 차단, 정책 상태로 초기화, 사용자 전체 권한 일괄 변경 때문에 `all`이
`default`로 바뀌는 경우도 `data_scope_change`에 기록됩니다.
앱 접근권한을 회수해도 선택 소속 grant는 보존되지만 실효 권한은 없습니다. 앱 접근권한을
다시 부여하면 보존된 grant가 다시 적용되므로 관리 UI에서 이 상태를 별도로 표시합니다.
활성·미만료 `policy`·`external` source grant는 관리 화면에서 읽기 전용이며 수동 교체
요청으로 덮어쓸 수 없습니다. 만료되었거나 비활성화된 자동 grant의 소속을 관리자가 다시
선택하면 해당 행은 `manual` source로 전환되고 전환 전후 값이 감사 로그에 남습니다.
Emails에서 `all`만으로 삭제·미분류 데이터 접근 특권이 생기지는 않으며, 해당 특권은
Emails `admin` 역할과 `all` 범위를 모두 가진 경우에만 활성화됩니다.

런타임 resolver는 먼저 앱 접근을 검사합니다. 접근이 없으면 grant가 존재해도 빈 범위를
반환합니다. `default`는 현재 소속 자동 포함 정책과 활성·미만료 앱별 grant의 합집합,
`all`은 모든 활성 소속입니다.

`UserAccess`와 `AccessPolicyRule`의 쓰기 경로는 이 Portal 권한 관리 API 하나입니다.
Django Admin에서는 두 모델을 조회만 할 수 있습니다. `AccessScope` 신규 정의는
코드와 migration으로만 추가합니다. Admin에서는 기존 scope의 이름·활성 상태·요청 가능
여부만 변경할 수 있고 `key`·유형 변경과 물리 삭제는 허용하지 않습니다. 사용자와 scope의
사용 중단은 삭제 대신 `is_active=false`로 처리하며 변경은 동일한 `AccessAuditLog` 형식으로
기록됩니다.

권한 부족 오류도 Portal과 앱이 같은 형태입니다.

```json
{
  "error": "scope_access_required",
  "scope": "appstore",
  "access": {
    "allowed": false,
    "scope": "appstore"
  }
}
```

## 사용자 검색

```http
GET /api/v1/account/users?search=kim&contactField=email
```

쿼리:

| Query | 설명 |
| --- | --- |
| `search` | 사용자 검색어 |
| `user_sdwt_prod`, `userSdwtProd` | 소속 필터 |
| `contactField` | `email` 또는 `knox_id` |
| `limit` | 숫자 또는 조건부 `all` |

## 외부 소속 동기화

```http
POST /api/v1/account/external-affiliations/sync
Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>
Content-Type: application/json
```

```json
{
  "records": [
    {
      "knox_id": "knox.user",
      "department": "Dept",
      "line": "Line",
      "user_sdwt_prod": "G-A",
      "source_updated_at": "2026-05-08T00:00:00Z"
    }
  ]
}
```

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 소속/입력 |
| 401 | 로그인 필요 |
| 403 | 관리/승인 권한 없음 |
| 404 | 대상 사용자 또는 변경 요청 없음 |
| 409 | 재확인 대상이 아님 |

## 관련 모듈 문서

- `docs/modules/account.md`
