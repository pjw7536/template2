# Work Hub API

## 인증

| Endpoint | 인증 |
| --- | --- |
| `GET /auth/grist/login` | Portal session + Portal/`work-hub` access + 허용된 Grist return URL |
| `GET /auth/grist/verify` | Nginx 내부 subrequest + 30초 서명 ticket + 현재 Portal/`work-hub` access |
| `GET /api/v1/work-hub/context` | Django session + Portal access + `work-hub` app access |
| `POST /api/v1/work-hub/webhooks/grist` | document·table 전용 Bearer token |

Grist API key와 Webhook 마스터 secret은 브라우저 응답에 포함하지 않습니다.

## GET `/auth/grist/login`, `/auth/grist/verify`

`login`은 `return_url`이 설정된 Grist public origin의 `/auth/login`인지 검증합니다. Portal session이 없으면 기존 Portal 로그인으로 이동하고, 로그인 후 활성 `account.User` PK를 최대 30초의 서명 ticket으로 만들어 Grist proxy에 반환합니다. `verify`는 외부에 직접 사용하는 API가 아니라 Nginx `auth_request`용 endpoint입니다. ticket의 현재 account와 Portal/`work-hub` 접근을 다시 검사하고 성공할 때만 204와 `X-Portal-User-Email`을 반환합니다. 미승인·비활성·email 누락은 403/401이며 잘못된 return origin은 400입니다.

## GET `/api/v1/work-hub/context`

현재 사용자가 열 수 있는 활성 Grist document mapping을 반환합니다. 일반 사용자는 Keycloak 기본 소속만, `work-hub-admin`은 모든 활성 mapping을 반환합니다.

```json
{
  "enabled": true,
  "available": true,
  "mode": "single",
  "reason": "",
  "groups": [
    {
      "user_sdwt_prod": "SDWT-A",
      "department": "ETCH",
      "line": "L1",
      "role": "member",
      "launch_url": "http://localhost:8100/o/work-hub/doc/abc123/p/3"
    }
  ]
}
```

| `mode` | 의미 |
| --- | --- |
| `disabled` | `WORK_HUB_ENABLED=0` |
| `unavailable` | 현재 허용 소속에 활성 Grist mapping이 없음 |
| `single` | 자동 이동할 mapping 1개 |
| `multiple` | `work-hub-admin`이 선택할 mapping 여러 개 |

주요 오류는 미인증 401, Portal 또는 `work-hub` scope 미승인 403입니다. Grist가 중지되어도 이 endpoint와 기존 Portal API는 동작하며, 실제 document 이동만 실패합니다.

## POST `/api/v1/work-hub/webhooks/grist`

Query에 `doc_id`와 `table_id`가 필요하며 body는 Grist가 보내는 평탄한 record 배열입니다.

```http
POST /api/v1/work-hub/webhooks/grist?doc_id=abc123&table_id=WorkLog
Authorization: Bearer <document-table-scoped-token>
Content-Type: application/json
```

Bearer token은 `GRIST_WEBHOOK_SECRET` 원문이 아니라 document ID와 table ID를 함께 사용해 파생한 값입니다. 운영자는 `configure_grist_scope --show-webhook-authorization`으로 해당 Webhook 값만 명시적으로 확인합니다. 다른 document나 table의 요청에는 같은 token을 사용할 수 없습니다.

```json
[
  {
    "id": 77,
    "follow_up_required": true,
    "task": 0,
    "archived": false,
    "equipment": 2,
    "symptom": "온도 이상",
    "action": "원인 점검"
  }
]
```

성공 응답:

```json
{
  "event_id": "grist:<payload-sha256>",
  "duplicate": false,
  "status": "received"
}
```

성공적으로 접수하면 외부 Grist API를 호출하지 않고 `202 Accepted`를 반환합니다. `work-hub-access-worker`가 저장된 작업을 임대해 처리하고 재시도 가능한 실패에는 최대 15분의 지수 backoff를 적용합니다. worker가 중단된 `processing` 작업은 2분 뒤 회수하며, 8회 실패하거나 재시도할 수 없는 설정·Grist 오류는 `terminal`로 보존합니다.

Grist Webhook에는 고유 event ID가 없으므로 document, table, record payload의 SHA-256을 event ID로 사용합니다. 같은 payload가 이미 접수됐으면 `duplicate=true`를 반환합니다. 진행 중인 작업은 그대로 두고 즉시 응답하며, 완료·실패 작업의 재전송은 다시 queue에 넣어 Task를 중복 생성하지 않는 범위에서 WorkLog의 Task 참조를 확인·연결합니다. 로컬 link가 가리키는 Task가 Grist에서 삭제되었으면 같은 `task_key`로 새 Task를 생성해 연결을 복구합니다. `WORK_HUB_ENABLED=0`이면 유효한 Webhook token도 403으로 거부하고 활성 mapping이 없으면 422를 반환합니다. 비동기 처리에 필요한 검증된 payload는 receipt에 저장하며 완료 이력은 기본 30일, 실패·terminal 이력은 기본 90일 뒤 정리합니다.

Task key는 `grist-worklog:<doc_id>:<worklog_table_id>:<worklog_row_id>`입니다. 로컬 link가 없더라도 Task table에서 이 key를 먼저 찾아 응답 유실에 의한 중복 생성을 막습니다.
