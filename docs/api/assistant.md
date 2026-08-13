# Assistant API

Assistant API는 versioned Profile과 permission-aware memory를 사용해 Portal, Email RAG, Observer 실행을 하나의 Turn 계약으로 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

Django session이 필요합니다. `knox_id`가 없는 사용자는 접근이 제한될 수 있습니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/v1/assistant/turns/stream` | Profile 기반 표준 Turn 실행·완료 replay SSE |
| GET | `/api/v1/assistant/rag-indexes` | 선택 가능한 RAG 인덱스/권한 그룹 |
| GET, POST | `/api/v1/assistant/conversations` | 현재 사용자의 대화방 목록·생성 |
| PATCH, DELETE | `/api/v1/assistant/conversations/<uuid>` | 이름·고정·보관 갱신 또는 삭제 |
| GET, DELETE | `/api/v1/assistant/conversations/<uuid>/messages` | 최근 메시지 조회·전체 초기화 |
| PUT, DELETE | `/api/v1/assistant/conversations/<uuid>/messages/<clientId>/feedback` | Assistant 답변 평가·취소 |
| GET | `/api/v1/assistant/conversations/<uuid>/export?exportFormat=markdown\|csv` | 현재 대화 분기 내보내기 |
| POST | `/api/v1/assistant/conversations/<uuid>/generate-title` | 저장된 대화로 OpenWebUI 업무용 제목 생성 |
| POST | `/api/v1/assistant/conversations/<uuid>/refresh-summary` | 기억 그룹별 장기 대화 요약 갱신 |

## 화면별 사용

| 화면 | API | 처리 방식 |
| --- | --- | --- |
| `/emails/*` | `/api/v1/assistant/turns/stream` | `email-rag` Profile로 RAG 검색과 답변 실행 |
| Observer 조회 context | `/api/v1/assistant/turns/stream` | `observer-analysis` Profile로 현재 데이터를 재조회해 분석 |
| 그 외 전역 ChatWidget, `/assistant` | `/api/v1/assistant/turns/stream` | `portal-default` Profile로 서버 memory를 사용해 실행 |

실행과 user/assistant 메시지 저장은 Turn endpoint만 담당합니다. 클라이언트가 별도 실행 이력이나 완료 메시지를 주입하는 API는 제공하지 않습니다.

## 표준 Turn API

```http
POST /api/v1/assistant/turns/stream
Content-Type: application/json
Accept: text/event-stream
```

```json
{
  "action": "send",
  "conversationId": "conversation-uuid",
  "clientRequestId": "request-uuid",
  "profileKey": "email-rag",
  "profileVersion": 1,
  "appContextKey": "assistant",
  "message": {"clientId": "user-client-id", "content": "최근 메일 요약"},
  "toolInputs": {
    "rag.search": {
      "permissionGroups": ["group-a", "rag-public"],
      "ragIndexes": ["rp-emails"]
    }
  }
}
```

Profile 계약:

| Profile | Provider/Tool | 읽기 partition | 쓰기 partition | Account scope |
| --- | --- | --- | --- | --- |
| `portal-default` v2 | OpenWebUI | `shared`, `scope:emails`, `scope:observer` | `shared` | `assistant` |
| `email-rag` | OpenWebUI + `rag.search` | `shared`, `scope:emails` | `scope:emails` | `assistant`, `emails` |
| `observer-analysis` | `observer.analysis` 현재 데이터 재조회 | `shared`, `scope:observer` | `scope:observer` | `assistant`, `observer` |

`portal-default` v2는 같은 대화방에서 앱 지식 모드에서 일반 대화로 전환해도 문맥을 잇기 위해 scoped partition을 읽습니다. scoped 메시지와 요약은 Provider에 전달하기 전에 저장 당시의 Account/data 권한을 현재 사용자 기준으로 다시 검증하며, 일반 대화의 새 메시지는 계속 `shared`에만 기록합니다. 과거 실행 재현을 위한 v1은 `shared`만 읽습니다.

`action`은 `send`, `edit`, `regenerate`, `retry`를 지원합니다. `edit`/`regenerate`는 `targetMessageId`, `retry`는 `retryRunId`가 필요하고 모든 재실행은 새 `clientRequestId`와 user `clientId`를 사용합니다. regenerate/retry는 저장된 Profile 버전과 제한된 Tool 입력을 재사용하지만 현재 Profile/Tool 권한 하한을 다시 적용합니다.

`appContextKey`는 prompt 출처이며 생략하거나 알 수 없는 앱으로 대신 실행할 수 없습니다. Portal은 `assistant:openwebui:<등록 앱>`, Email은 `assistant`, Observer는 현재 Tool 입력에서 계산한 `observer:v1:<sha256>`만 허용합니다.

표준 SSE event는 `run.started`, `tool.started`, `tool.completed`, `run.heartbeat`, `message.delta`, `message.completed`, `run.completed`, `run.failed`입니다. Portal 답변은 외부 OpenAI 호환 chunk가 도착하는 대로 `message.delta`로 전달합니다. 구조화 검증이 필요한 Email/Observer는 전체 JSON 검증을 통과한 뒤 표시 가능한 block을 전달합니다. 같은 `clientRequestId`와 동일 hash의 완료 Run은 현재 권한 재검증 뒤 저장된 `message.completed`만 replay합니다. branch, 메시지, summary는 변경하지 않습니다. 다른 hash 또는 미완료 Run은 409입니다.

## RAG 인덱스 목록

```http
GET /api/v1/assistant/rag-indexes
```

응답에는 사용자가 선택할 수 있는 RAG index, 기본 index, Email scope에서 계산한 permission group이 포함됩니다. mailbox claim은 서버가 같은 Email scope에서 계산하므로 클라이언트가 제출하지 않습니다.

## 사용자별 대화방 저장

대화방 생성:

```http
POST /api/v1/assistant/conversations
Content-Type: application/json

{"name": "장비 문의"}
```

서버가 UUID를 발급하며 목록과 메시지는 로그인 사용자 본인 데이터만 반환합니다. user/assistant 메시지는 Turn service가 같은 Run 안에서 저장합니다.

- `clientId`는 `(conversation, clientId)` unique constraint로 중복 저장을 방지합니다.
- user와 assistant `content`는 각각 최대 10,000자입니다.
- 메시지 `sources`는 50개와 직렬화 기준 50KB, `contextSnapshot`은 100KB까지 허용합니다.
- 생성 답변은 화면 표시와 저장 전에 같은 상한으로 정리됩니다. 상한을 넘은 본문에는 생략 안내를 표시합니다.
- `blocks`는 최대 20개, JSON 50KB, 전체 `sourceIds` 50개이며 `content`는 block을 합친 10,000자 이내 정규화 표현입니다. source 원문을 block에 중복하지 않습니다.
- `contextKey`는 레거시 출처 식별에만 사용합니다. 권한과 Profile 선택에는 사용하지 않습니다.
- `parentId`와 `revisionOfId`는 질문 수정·답변 재생성 시 원본을 삭제하지 않는 분기 관계입니다. GET은 현재 활성 분기만 반환합니다.
- Observer 답변은 원본 로그 전체 대신 제한된 `contextSnapshot`의 조회 범위, 집계 coverage, 근거 ID를 저장합니다.
- 대화방 GET은 `search`, `cursor`, `limit`, `archived`를 지원하고 검색은 제목과 메시지 본문을 함께 확인합니다. 고정 대화방은 전체 cursor page에서 일반 대화방보다 먼저 정렬됩니다. 메시지 GET은 `before`, `limit`으로 과거 page를 조회합니다.
- 목록 응답은 공통으로 `results`, `nextCursor`, `hasMore`를 반환합니다. cursor는 서버가 서명한 opaque 문자열이므로 클라이언트가 해석하지 않습니다.
- 메시지 DELETE는 방은 유지하고 내용을 초기화하며, 대화방 DELETE는 메시지까지 cascade 삭제합니다.

최근 10개를 제외한 같은 partition 메시지가 12개 이상 새로 쌓이면 다음 endpoint가 오래된 이력을 rolling summary로 갱신합니다. Portal, Email, Observer partition은 서로 섞지 않습니다.

```http
POST /api/v1/assistant/conversations/<uuid>/refresh-summary
Content-Type: application/json

{"contextKey": "profile:portal-default"}
```

요약은 최대 2,000자로 `(conversation, memory_partition)`별 저장하며 포함 메시지의 `access_requirements` 합집합을 보존합니다. 요약 생성 중 branch head가 바뀌면 결과를 폐기합니다.

첫 질문과 답변 저장 후 기본 이름인 방은 다음 endpoint로 제목을 생성합니다.

```http
POST /api/v1/assistant/conversations/<uuid>/generate-title
```

request body는 없으며 응답은 갱신된 대화방 metadata입니다.

```json
{
  "id": "conversation-uuid",
  "name": "EQP DOWN 반복 원인 분석",
  "pinned": false,
  "archived": false,
  "createdAt": "2026-08-11T04:00:00Z",
  "updatedAt": "2026-08-11T04:01:00Z"
}
```

- `새 대화`, `새 대화 N` 형식의 기본 이름만 자동 변경합니다.
- OpenWebUI에는 저장된 최근 메시지 중 최대 6개가 전달됩니다.
- 제목은 핵심 업무 주제 중심의 명사형 2~7어절로 요청하며 최대 40자로 정규화합니다.
- 제목 생성 실패는 기존 메시지 저장과 답변 표시를 취소하지 않습니다.

## Run 중복 방지와 종료 처리

Turn service가 `clientRequestId`와 요청 hash를 원자적으로 확인해 중복 실행을 막습니다. 완료·사용자 중단·요청 실패는 각각 `completed`, `stopped`, `failed`로 기록하고, 연결이 끊기거나 timeout이 발생하면 upstream response/session을 닫은 뒤 Run을 `stopped` 처리합니다. 완료 저장 직전에는 활성 Run, lease 만료, 예상 branch head를 다시 잠금 검증하므로 늦게 도착한 결과는 저장되지 않습니다. 브라우저가 별도 lease를 획득하거나 종료 상태를 보정하는 API는 없습니다.

## 대화 관리와 내보내기

- 대화방 PATCH는 `name`, `pinned`, `archived` 중 하나 이상을 받습니다.
- 답변 평가는 `rating: up|down`과 선택적 `reason`을 메시지별 하나만 저장합니다.
- `exportFormat=markdown`은 읽기용 문서, `exportFormat=csv`는 Excel 호환 UTF-8 BOM CSV를 반환합니다.
- CSV의 사용자 입력 셀은 `=`, `+`, `-`, `@` 등으로 시작할 때 Excel 수식으로 실행되지 않도록 텍스트 처리합니다.
- 수정·재생성으로 분기가 생긴 경우 내보내기와 rolling summary에는 현재 활성 분기만 사용합니다.

## 권한 규칙

Turn endpoint는 Django session과 Profile별 Account scope를 검사합니다. Email Tool의 permission group 선택·검색·저장·재검증은 모두 `emails` scope에서 서버가 계산한 접근 가능 그룹을 기준으로 합니다. `assistant` scope 소속은 Email 검색 범위를 넓히지 않습니다.

대화방 endpoint는 UUID만으로 접근할 수 없으며 항상 `conversation.user == request.user` 조건을 적용합니다. 다른 사용자의 방은 존재 여부를 노출하지 않고 404를 반환합니다.

Run, 메시지, 요약, 자동 제목은 version 1 `access_requirements`에 Account scope와 `ragPermissionGroups`/`mailboxes` data claim을 저장합니다. 조회·검색·내보내기·feedback·edit·regenerate·retry·replay마다 현재 권한을 다시 검사합니다. 하나라도 회수되면 답변 전체를 잠그고 내부 group/mailbox 이름은 반환하지 않습니다. 잠긴 메시지는 ID, role, 생성 시각, parent/revision/Run 관계만 반환하고 본문·block·source·context snapshot은 제외합니다. 내보내기는 일반 권한 제외 문구로 대체합니다.

legacy provenance는 `backfill_assistant_run_access --dry-run --batch-size N --checkpoint-file <path>`로 분류합니다. command는 재실행 가능하며 해석 불가능한 데이터는 `legacy-unresolved` synthetic Run에 연결해 계속 잠급니다.

서버가 기본으로 계산하는 그룹:

- Emails scope에서 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수 Turn 필드 누락, 형식 오류 |
| 401 | 로그인 필요 |
| 403 | permission group 접근 불가 또는 `knox_id` 없음 |
| 404 | 본인 소유가 아닌 대화방 또는 존재하지 않는 대화방 |
| 409 | 멱등성 충돌, 미완료 Run replay 또는 제목 생성에 필요한 대화 부족 |
| 502 | RAG 또는 OpenWebUI 호출 실패 |
| 503 | RAG 또는 OpenWebUI 설정 누락 |

## 관련 모듈 문서

- `docs/modules/assistant.md`
