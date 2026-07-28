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
| GET/POST | `/api/v1/account/affiliation/reconfirm` | Session | 외부 예측 소속 재확인 |
| POST | `/api/v1/account/external-affiliations/sync` | Bearer token | 외부 예측 소속 동기화 |
| POST | `/api/v1/account/access/request` | Session | 내 Portal·앱·기능 scope 접근 신청 |
| GET | `/api/v1/account/access/users` | Session + Portal admin | scope별 사용자 접근 현황 |
| GET | `/api/v1/account/access/matrix` | Session + Portal admin | 사용자별 Portal·활성 하위 scope 권한 매트릭스 |
| POST | `/api/v1/account/access/users/<user_id>/decision` | Session + Portal admin | Portal·앱·기능 권한 승인/거절/부여/회수/역할 변경 |
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

```json
{
  "user_sdwt_prod": "G-A",
  "userId": 55,
  "action": "grant",
  "role": "manager"
}
```

허용 role:

- `viewer`
- `member`
- `manager`

대상 사용자 키:

- `userId`
- `user_id`
- `knox_id`

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

대기 요청은 `approve` 또는 `reject`, 일반 수동 변경은 `grant`, `revoke`, `reset_to_policy`, `change_role`을 사용합니다. `role`을 생략한 승인·부여는 항상 `user`가 됩니다. Portal 승인에서만 `approveAllApps: true`를 선택해 명시 차단되지 않은 활성 앱을 `user`로 함께 허용할 수 있습니다.

잘못된 JSON body는 모든 접근 API에서 `{"error":"invalid_request","details":{...}}`, 잘못된 query는 `{"error":"invalid_query","details":{...}}` 형태로 반환합니다.

앱 관리자 기능은 모두 같은 기준을 사용합니다.

| Scope `admin` | 관리자 기능 |
| --- | --- |
| `appstore` | 다른 사용자의 앱·댓글 관리 |
| `l3-spider` | 개발자 옵션 조회 |
| `line-dashboard` | Drone target 기준 정보 관리 |
| `emails` | 전체·미분류 메일함 관리 |
| `access-stats` | 수동 통계 입력과 외부 통계 동기화 |
| `voc` | 다른 사용자의 게시글 관리 |

`is_staff`는 앱 관리자 판정에 사용하지 않습니다.

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
