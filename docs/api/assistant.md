# Assistant API

Assistant API는 화면에 따라 일반 OpenWebUI 대화와 메일 RAG 답변을 분리해 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

Django session이 필요합니다. `knox_id`가 없는 사용자는 접근이 제한될 수 있습니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/assistant/rag-indexes` | 선택 가능한 RAG 인덱스/권한 그룹 |
| POST | `/api/v1/assistant/chat` | 메일함 RAG 답변 생성 |
| POST | `/api/v1/assistant/openwebui-chat` | 메일함 외 화면의 OpenWebUI 답변 생성 |
| POST | `/api/v1/assistant/openwebui-chat/stream` | 메일함 외 화면의 OpenWebUI SSE 답변 생성 |
| GET, POST | `/api/v1/assistant/conversations` | 현재 사용자의 대화방 목록·생성 |
| PATCH, DELETE | `/api/v1/assistant/conversations/<uuid>` | 이름·고정·보관 갱신 또는 삭제 |
| GET, POST, DELETE | `/api/v1/assistant/conversations/<uuid>/messages` | 최근 메시지 조회·멱등 추가·전체 초기화 |
| PUT, DELETE | `/api/v1/assistant/conversations/<uuid>/messages/<clientId>/feedback` | Assistant 답변 평가·취소 |
| GET | `/api/v1/assistant/conversations/<uuid>/export?exportFormat=markdown\|csv` | 현재 대화 분기 내보내기 |
| POST | `/api/v1/assistant/conversations/<uuid>/generate-title` | 저장된 대화로 OpenWebUI 업무용 제목 생성 |
| POST | `/api/v1/assistant/conversations/<uuid>/refresh-summary` | 기억 그룹별 장기 대화 요약 갱신 |
| GET, POST | `/api/v1/assistant/generations` | 사용자 활성 생성 조회·lease 획득 |
| PATCH | `/api/v1/assistant/generations/<uuid>` | 생성 완료·중단·실패 기록 |

## 화면별 사용

| 화면 | API | 처리 방식 |
| --- | --- | --- |
| `/emails/*` | `/api/v1/assistant/chat` | RAG 검색 후 기존 Assistant LLM 호출 |
| Observer 조회 context | `/api/v1/observer/analysis` | 조회 데이터를 구조화해 OpenWebUI 분석 |
| 그 외 전역 ChatWidget, `/assistant` | `/api/v1/assistant/openwebui-chat/stream` | 대화 이력을 OpenWebUI에 전달하고 SSE로 표시 |

## RAG 인덱스 목록

```http
GET /api/v1/assistant/rag-indexes
```

응답에는 사용자가 선택할 수 있는 RAG index, 기본 index, permission group이 포함됩니다.

## 메일 RAG 채팅 요청

```http
POST /api/v1/assistant/chat
Content-Type: application/json
```

```json
{
  "prompt": "최근 메일에서 이슈 요약해줘",
  "roomId": "room-1",
  "ragIndexName": ["rp-emails"],
  "permissionGroups": ["G-A", "knox.user"]
}
```

주요 필드:

| Field | 설명 |
| --- | --- |
| `prompt` | 사용자 질문 |
| `roomId` | 대화방 식별자 |
| `history` | 선택적 대화 이력 |
| `ragIndexName` | 검색할 RAG 인덱스(문자열 또는 배열) |
| `permissionGroups` | 검색 허용 그룹 |

`history`는 최근 대화 최대 20개를 받으며 각 `content`는 최대 10,000자입니다.

## OpenWebUI 일반 채팅 요청

```http
POST /api/v1/assistant/openwebui-chat
Content-Type: application/json
```

```json
{
  "prompt": "장비 예방 정비 체크리스트를 알려줘",
  "roomId": "room-1",
  "contextKey": "assistant:openwebui",
  "history": [
    {"role": "user", "content": "이전 질문"},
    {"role": "assistant", "content": "이전 답변"}
  ]
}
```

`permissionGroups`와 `ragIndexName`은 OpenWebUI 일반 채팅에서 사용하지 않습니다. 서버는 사용자/assistant role만 대화 이력으로 허용하고 고정 system message를 추가합니다.

ChatWidget은 같은 payload를 `/openwebui-chat/stream`에 전송합니다. 응답은 `text/event-stream`이며 event 계약은 다음과 같습니다.

| Event | Data | 설명 |
| --- | --- | --- |
| `meta` | `provider`, `ragConfigured` | 공급자 정보 |
| `delta` | `content` | 화면에 즉시 이어 붙일 답변 조각 |
| `done` | `reply`, `historyCount` | 최종 답변과 서버 이력 수 |
| `error` | `error` | stream 시작 후 발생한 오류 |

브라우저는 `done` event를 받은 경우에만 완성된 응답으로 처리합니다. `delta`만 수신한 상태에서 연결이 종료되면 일부 답변을 저장하지 않고 오류로 안내합니다. 브라우저가 연결을 중지하면 upstream OpenWebUI 연결도 닫습니다. 기존 JSON endpoint는 호환을 위해 유지합니다.

## 사용자별 대화방 저장

대화방 생성:

```http
POST /api/v1/assistant/conversations
Content-Type: application/json

{"name": "장비 문의"}
```

서버가 UUID를 발급하며 목록과 메시지는 로그인 사용자 본인 데이터만 반환합니다. 메시지 저장 예시는 다음과 같습니다.

```http
POST /api/v1/assistant/conversations/<uuid>/messages
Content-Type: application/json
```

```json
{
  "messages": [
    {
      "clientId": "user-1720000000000-ab12c",
      "role": "user",
      "content": "DOWN 반복 원인을 알려줘",
      "contextKey": "assistant:openwebui",
      "sources": [],
      "parentId": null,
      "revisionOfId": null
    }
  ]
}
```

- `clientId`는 `(conversation, clientId)` unique constraint로 중복 저장을 방지합니다.
- 한 요청은 메시지 20개까지 저장할 수 있으며 `content`와 채팅 `prompt`는 각각 최대 10,000자입니다.
- 메시지 `sources`는 50개와 직렬화 기준 50KB, `contextSnapshot`은 100KB까지 허용합니다.
- 생성 답변은 화면 표시와 저장 전에 같은 상한으로 정리됩니다. 본문이 줄어들면 생략 안내를 표시하고, 저장 재시도도 실패하면 해당 미저장 답변만 제거해 다음 질문을 계속할 수 있습니다.
- `contextKey`는 일반 OpenWebUI, Email RAG, Observer 조회 context의 요청 경로·메시지 출처·현재 데이터 범위를 구분합니다. 같은 방의 일반 OpenWebUI와 Observer는 모델 입력 이력을 공유하며 Email RAG는 분리합니다.
- `parentId`와 `revisionOfId`는 질문 수정·답변 재생성 시 원본을 삭제하지 않는 분기 관계입니다. GET은 현재 활성 분기만 반환합니다.
- Observer 답변은 원본 로그 전체 대신 제한된 `contextSnapshot`의 조회 범위, 집계 coverage, 근거 ID를 저장합니다.
- 대화방 GET은 `search`, `cursor`, `limit`, `archived`를 지원하고 검색은 제목과 메시지 본문을 함께 확인합니다. 고정 대화방은 전체 cursor page에서 일반 대화방보다 먼저 정렬됩니다. 메시지 GET은 `before`, `limit`으로 과거 page를 조회합니다.
- 목록 응답은 공통으로 `results`, `nextCursor`, `hasMore`를 반환합니다. cursor는 서버가 서명한 opaque 문자열이므로 클라이언트가 해석하지 않습니다.
- 메시지 DELETE는 방은 유지하고 내용을 초기화하며, 대화방 DELETE는 메시지까지 cascade 삭제합니다.

최근 10개를 제외한 같은 기억 그룹 메시지가 12개 이상 새로 쌓이면 다음 endpoint가 오래된 이력을 rolling summary로 갱신합니다. `assistant:openwebui`와 `observer:*`는 `chatwidget:shared` 그룹으로 함께 집계하고 `assistant` Email RAG는 별도로 집계합니다.

```http
POST /api/v1/assistant/conversations/<uuid>/refresh-summary
Content-Type: application/json

{"contextKey": "assistant:openwebui"}
```

요약은 최대 2,000자로 `assistant_conversation_summary`에 `(conversation, memory context key)`별로 저장합니다. 같은 방의 일반 Chat·Observer 요청에는 `chatwidget:shared` 요약을 주입하고 Email RAG와 다른 방에는 주입하지 않습니다. Observer는 이 요약을 질문 의도 파악용 배경으로만 사용하고 현재 조회 데이터만 사실 근거로 사용합니다. 요약 실패는 이미 완료된 답변과 메시지 저장을 취소하지 않습니다.

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

## 생성 중복 방지와 종료 처리

브라우저는 모델을 호출하기 전에 `/generations`에서 사용자 단위 lease를 획득합니다. 같은 사용자가 다른 탭이나 대화방에서 이미 생성 중이면 서버가 409와 활성 generation 정보를 반환합니다. 완료·사용자 중단·요청 실패는 각각 `completed`, `stopped`, `failed`로 종료합니다. generation이 연결된 Assistant 답변은 메시지 저장과 같은 transaction에서 `completed` 처리하므로 브라우저의 후속 종료 요청이 실패해도 lease가 남지 않습니다.

새로고침이나 탭 종료 시 브라우저는 `keepalive` 요청으로 현재 generation을 `client_disconnected` 실패 처리합니다. 비정상 종료로 요청이 전달되지 않아도 180초 lease가 만료되며 다음 획득 시 실패 상태로 정리됩니다. 백그라운드 생성 지속과 SSE 재연결은 1차 범위에 포함하지 않습니다.

## 대화 관리와 내보내기

- 대화방 PATCH는 `name`, `pinned`, `archived` 중 하나 이상을 받습니다.
- 답변 평가는 `rating: up|down`과 선택적 `reason`을 메시지별 하나만 저장합니다.
- `exportFormat=markdown`은 읽기용 문서, `exportFormat=csv`는 Excel 호환 UTF-8 BOM CSV를 반환합니다.
- CSV의 사용자 입력 셀은 `=`, `+`, `-`, `@` 등으로 시작할 때 Excel 수식으로 실행되지 않도록 텍스트 처리합니다.
- 수정·재생성으로 분기가 생긴 경우 내보내기와 rolling summary에는 현재 활성 분기만 사용합니다.

## 응답

```json
{
  "reply": "답변",
  "contexts": [],
  "sources": [],
  "segments": [],
  "meta": {"provider": "openwebui"}
}
```

## 권한 규칙

두 채팅 endpoint 모두 Django session과 Assistant 접근 권한을 사용하며 `knox_id`가 필요합니다. 메일 RAG 요청의 permission group은 서버가 계산한 접근 가능 그룹 안에 있어야 합니다.

대화방 endpoint는 UUID만으로 접근할 수 없으며 항상 `conversation.user == request.user` 조건을 적용합니다. 다른 사용자의 방은 존재 여부를 노출하지 않고 404를 반환합니다.

서버가 기본으로 계산하는 그룹:

- 사용자의 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

## 오류

| Status | 상황 |
| --- | --- |
| 400 | prompt 누락, 형식 오류 |
| 401 | 로그인 필요 |
| 403 | permission group 접근 불가 또는 `knox_id` 없음 |
| 404 | 본인 소유가 아닌 대화방 또는 존재하지 않는 대화방 |
| 409 | 제목 생성에 필요한 대화가 부족하거나 같은 사용자의 다른 생성이 진행 중 |
| 502 | RAG/LLM 또는 OpenWebUI 호출 실패 |
| 503 | RAG/LLM 또는 OpenWebUI 설정 누락 |

## 관련 모듈 문서

- `docs/modules/assistant.md`
