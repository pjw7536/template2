# Assistant·RAG

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


Assistant는 일반 질문에 답하고, 메일·설비·앱 목록·대시보드에서 현재 업무 자료를 근거로 대화하는 기능입니다.
전체 대화 화면과 각 화면의 ChatWidget은 같은 대화 실행 경로를 사용합니다.
질문을 보내면 답변이 스트리밍으로 표시되고, 대화 이력은 사용자별 대화방에 저장됩니다.

업무 자료를 얻는 방법은 화면에 따라 다릅니다. 메일함은 RAG 검색 결과를 사용하고,
Appstore·ESOP·Observer는 서버가 현재 조회 조건과 권한을 확인해 자료를 다시 조회합니다.
답변 생성은 OpenWebUI 연결을 사용합니다. RAG app은 외부 검색 서버를 호출하는 공통 client입니다.

아래의 Profile은 화면별 대화 처리 규칙, partition은 같은 대화방 안에서 권한에 따라 구분한 기억 영역을 뜻합니다.
일반 대화·업무 자료·기억을 섞어 읽지 않도록 구분하며, 세부 권한과 실행 흐름을 이어서 설명합니다.

### 기능 요약

- 사용 가능한 RAG index 조회
- permission group 검증
- 메일함 RAG 검색과 OpenWebUI 호출
- 일반 화면 OpenWebUI 대화
- Appstore 앱 검색·상세 조건 기반 카탈로그 배경지식
- ESOP Dashboard line·기간 기반 상태/이력 배경지식
- 정규화된 답변 block과 출처 반환
- 사용자/대화방 UUID 단위 DB 대화 이력 관리
- OpenWebUI 기반 업무용 대화방 제목 자동 생성
- SSE 답변 표시·중단·실패 재시도
- cursor 기반 대화방 검색·과거 메시지 조회와 Profile partition별 장기 요약
- versioned Profile, access requirements, 표준 Turn SSE와 완료 replay
- Turn 요청 hash와 Run 원자성 기반 중복 방지
- 질문 편집·답변 재생성 분기, 메시지 복사·평가
- 대화방 이름 변경·고정·보관, 현재 목록 전체 선택 삭제와 제목·본문 통합 검색
- Observer 범위·coverage·분석 버전·이동 가능한 근거 snapshot 표시와 Markdown·CSV 내보내기

### 권한 기준

Email RAG는 다음 값을 permission group으로 사용합니다.

- Emails scope에서 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

요청 permission group이 이 범위를 벗어나면 거부합니다. Portal의 Assistant scope 소속은 Email RAG 검색 범위로 사용하지 않습니다.

### 일반 화면 OpenWebUI 흐름

1. 전역 ChatWidget이 현재 route를 확인합니다.
2. `/emails/*`, 유효한 Observer/Appstore/ESOP page context가 아니면 등록된 현재 앱의 `appContextKey`와 `portal-default` Profile로 표준 Turn을 요청합니다. 알 수 없는 route는 Portal로 추정하지 않고 Widget을 표시하지 않습니다.
3. 서버가 로그인 사용자와 `knox_id`를 확인합니다.
4. `portal-default` v2는 현재 대화방의 `shared` partition 요약과 최근 이력만 사용합니다. Email·Observer 등 앱별 partition은 해당 앱 Profile에서만 읽습니다.
5. 서버 허용 카탈로그의 현재 앱 배경지식, 같은 방에서 권한 검증을 통과한 저장 요약과 최근 이력을 합쳐 기존 `OPENWEBUI_*` 설정으로 OpenAI 호환 Chat Completions를 호출합니다.
6. 외부 OpenAI 호환 stream의 chunk를 `message.delta`로 즉시 표시하고, 대기 중에는 `run.heartbeat`를 보냅니다. 중단·disconnect·timeout이면 upstream 연결을 닫습니다.

`/assistant` 전체 화면도 같은 Turn client를 사용합니다. 일반 화면에서는 사용하지 않는 RAG index 조회와 설정 UI를 표시하지 않습니다.

### Appstore·ESOP 배경지식 흐름

1. Appstore는 검색어·카테고리·선택 앱 ID, ESOP는 status/history·line ID·기간만 page context로 등록합니다.
2. frontend는 원본 업무 데이터를 보내지 않고 제한된 Tool 입력만 표준 Turn으로 전송합니다.
3. 서버가 각각 `assistant+appstore`, `assistant+line-dashboard` Account scope를 검사합니다.
4. Appstore/Drone selector가 연락처·댓글·수신자·관리자 설정을 제외한 크기 제한 snapshot을 다시 조회합니다.
5. snapshot을 명령이 아닌 읽기 전용 JSON 자료로 표시해 기존 OpenWebUI stream에 전달합니다.
6. 답변과 요약은 각각 `scope:appstore`, `scope:line-dashboard`에 저장하고 모든 재사용 시점에 권한을 다시 검증합니다.

### 메일함 RAG 흐름

1. `/emails/*` 화면에서 `email-rag` Profile Turn을 요청합니다.
2. 서버가 사용자와 `knox_id`를 확인합니다.
3. Email scope에서 permission group과 mailbox claim을 서버가 계산하고 RAG index를 검증합니다.
4. 현재 대화방의 `shared`와 `scope:emails` partition에서 현재 권한을 통과한 이력만 가져옵니다.
5. RAG 검색을 수행합니다.
6. 검색 결과의 permission group/mailbox가 현재 서버 범위와 일치하는 문서만 `OPENWEBUI_*` 연결에 전달합니다.
7. OpenWebUI의 단일 `answer`/`segments` JSON 계약을 검증합니다. 일반 텍스트, 코드펜스, 구형 `usedEmailIds` 포맷은 답변으로 대신 사용하지 않습니다.
8. 검증된 답변 block, 출처와 안전한 Tool 통계를 표준 SSE로 반환합니다.

### RAG client 역할

- RAG 검색
- Email 문서 insert
- 문서 delete
- index/permission group 정규화
- 실패 로그 기록

### 대화방 영구 저장

#### 저장 모델과 분기

- `AssistantConversation`은 UUID와 user FK로 대화방 소유자를 고정합니다.
- `AssistantMessage`는 user/assistant role, 표시 content, context key, 출처와 parent/revision 관계를 저장합니다.
- `AssistantConversation.current_message`에서 parent를 따라간 경로가 현재 대화 분기이며 수정·재생성 전 원본도 DB에 보존합니다.
- `AssistantGeneration`은 Turn Run의 Profile, Tool, 권한 요구사항과 완료·중단·실패 상태를 기록합니다.
- `AssistantContextSnapshot`은 Observer 원본 행 대신 범위·coverage·분석 버전·근거 ID와 범위 복원 URL만 제한해 저장하고 `AssistantMessageFeedback`은 답변별 평가를 저장합니다.
- Observer 근거 패널은 분석 당시 범위와 현재 조회 범위가 같은지 표시하며, 근거 버튼으로 당시 조건을 복원한 Observer Data Log로 이동합니다.
#### 목록 조회와 이력 구성

- 방 목록은 검색 가능한 cursor page로 조회하고 활성 방의 최근 20개 메시지를 먼저 표시한 뒤 과거 page를 앞에 추가합니다.
- 모델 호출 전 user 메시지, 성공 후 assistant 메시지를 저장합니다.
- frontend는 서버 DB와 React Query를 원본으로 사용하며 `localStorage`를 사용하지 않습니다.
- 재접속 시 서버가 반환한 최신 대화방을 활성화하고, 메일 RAG 선택값은 현재 실행 중인 메모리에서만 유지합니다.
- 모델 입력 이력은 클라이언트에서 받지 않고 서버 DB current branch에서만 구성합니다. 따라서 인사 메시지나 앱 출처 접두사도 클라이언트가 모델 이력에 삽입하지 않습니다.
- 충분히 누적된 과거 메시지는 OpenWebUI 저비용 요청으로 최대 2,000자의 rolling summary를 만들고, Provider에는 summary cursor 이후의 최근 이력만 추가해 같은 메시지를 중복 전달하지 않습니다.
#### 기억 영역과 접근 권한

- 같은 대화방에서 일반 대화 `portal-default` v2는 `shared` 기억만 읽습니다. Email, Observer, Appstore, ESOP 전용 Profile은 `shared`와 자기 `scope:*` partition만 읽고, scoped 데이터는 `shared`에 기록하지 않습니다.
- 메시지·summary·자동 제목·Run은 현재 Account scope와 RAG group/mailbox data claim을 합친 `access_requirements`를 보존하고 모든 재사용 시점에 다시 검증합니다.
- 앱을 이동하면 대화방은 유지하고 현재 Profile이 허용한 기억 partition·Tool·화면 데이터만 사용합니다.
- Observer 분석에서는 공유 대화와 장기 요약을 질문 의도·용어·후속 질문을 이해하는 배경으로만 사용하고, 사실 판단은 현재 조회 조건의 `observer_analysis_context_json`만 근거로 삼습니다.
- 일반 답변·Email RAG·대화방 제목·장기 요약·Observer 분석은 공통 영문 업무 용어 guide를 사용합니다. 설명 문장은 한국어로 작성하되 `interlock`, `wafer lot`, `sample wafer`, `recipe`, `sensor` 같은 canonical 업무 용어는 번역하거나 한글로 음역하지 않습니다.
#### 중단·삭제와 화면 동작

- 새로고침·탭 종료로 SSE가 끊기면 Turn service가 upstream response/session을 닫고 Run을 중단 처리합니다. 완료 저장도 활성 lease와 branch head를 다시 확인합니다. 백그라운드 생성과 SSE 재연결은 제공하지 않습니다.
- 대화방 선택 모드는 현재 검색·보관 조건에서 불러온 방을 대상으로 하며, 생성 중인 방을 제외하고 기존 소유자 전용 DELETE API로 삭제합니다. 일부 요청이 실패하면 성공한 방만 제거하고 실패한 방은 재시도할 수 있게 남깁니다.
- 최초 `무엇을 도와드릴까요?` 인사에는 메시지 action을 표시하지 않습니다.
- ChatWidget의 대화방 메뉴·Dialog 같은 portal이 열려 있을 때 바깥 클릭은 portal만 닫고 ChatWidget 자체는 유지합니다.

### 대화방 제목 자동 생성

1. Turn service가 첫 user 메시지와 Assistant 답변을 DB에 저장합니다.
2. frontend는 `message.completed` 수신 후 `/conversations/<uuid>/generate-title`을 비동기로 호출합니다.
3. backend가 본인 소유 방인지 확인하고 저장된 최근 메시지를 조회합니다.
4. `새 대화` 계열 이름일 때만 기존 OpenWebUI 설정으로 제목을 요청합니다.
5. Markdown, 따옴표, 접두어와 종결 문장부호를 제거하고 최대 40자로 저장합니다.
6. frontend가 React Query 대화방 cache를 갱신해 목록에 즉시 반영합니다.

제목 형식은 핵심 주제 중심의 한국어 명사형 2~7어절입니다. 장비명, `DOWN`, `IDLE`, `L*_TIP` 같은 상태명과 기술 용어는 원문을 유지합니다. 제목 요청은 채팅 전송 상태와 분리하므로 실패하거나 지연되어도 답변 표시와 다음 질문을 막지 않습니다.

### 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/assistant` |
| Frontend | `apps/portal/web/src/features/assistant` |
| Backend API | `/api/v1/assistant/turns/stream`, `/api/v1/assistant/rag-indexes`, `/api/v1/assistant/conversations*` |
| 데이터 | Account 권한 그룹, `assistant_conversation`, `assistant_conversation_summary`, `assistant_message`, `assistant_generation`, `assistant_context_snapshot`, `assistant_message_feedback` |
| 외부 연동 | OpenWebUI 일반 대화·Email RAG 답변 SSE·대화방 제목·장기 요약 chat completions, RAG search |

### 운영 포인트

- 답변이 빈 경우 RAG index, permission group, RAG 검색 결과를 먼저 확인합니다.
- 일반 화면의 502/503은 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, token/header, timeout 설정을 확인합니다.
- 메일함의 403은 요청 permission group이 서버 계산 그룹을 벗어났거나 `knox_id`가 없을 때 발생할 수 있습니다.
- 메일함의 502/503은 RAG 설정과 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, token/header, timeout 설정을 확인합니다.

### 관련 API

- [Assistant API](#api)

### 관련 코드

- `apps/portal/api/api/assistant/views/`
- `apps/portal/api/api/assistant/services/chat.py`
- `apps/portal/api/api/assistant/services/config.py`
- `apps/portal/api/api/assistant/services/conversations.py`
- `apps/portal/api/api/assistant/services/generations.py`
- `apps/portal/api/api/assistant/services/exports.py`
- `apps/portal/api/api/assistant/services/normalization.py`
- `apps/portal/api/api/assistant/services/openwebui.py`
- `apps/portal/api/api/assistant/services/profiles.py`
- `apps/portal/api/api/assistant/services/access_requirements.py`
- `apps/portal/api/api/assistant/services/runtime.py`
- `apps/portal/api/api/assistant/services/turns.py`
- `apps/portal/api/api/assistant/services/runtime_execution.py`
- `apps/portal/api/api/assistant/services/runtime_memory.py`
- `apps/portal/api/api/assistant/services/turn_persistence.py`
- `apps/portal/api/api/assistant/services/reply.py`
- `apps/portal/api/api/rag/services/client.py`
- `apps/portal/api/api/rag/services/config.py`
- `apps/portal/api/api/appstore/selectors.py`
- `apps/portal/api/api/drone/selectors/`
- `apps/portal/web/src/features/assistant`

## API


Assistant API는 일반 대화, 메일 검색, Observer 분석과 Appstore·ESOP 화면 기반 답변을 제공합니다.
모든 질문은 같은 Turn API로 실행하며, 사용 목적에 맞는 Profile과 현재 권한에 따라 사용할 데이터와 대화 기억을 결정합니다.

### 주요 용어

| 용어 | 의미 |
| --- | --- |
| Turn | 질문 전송·편집·재생성 등 한 번의 실행 요청 |
| Profile | 사용할 도구, 대화 기억과 필요한 앱 권한을 정한 버전별 실행 규칙 |
| Run | Turn의 진행 상태·결과를 기록하는 실행 단위 |
| partition | 일반 대화와 앱별 대화 기억을 구분하는 저장 영역 |
| SSE | 실행 상태와 답변을 서버가 순차적으로 전달하는 스트리밍 방식 |

### 호출자

- 브라우저 SPA

### 인증

Django session과 Portal·`assistant` 앱 접근이 필요합니다. Profile별 추가 앱 권한과 `knox_id`도 검사합니다.

### Endpoint

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

### 화면별 사용

| 화면 | API | 처리 방식 |
| --- | --- | --- |
| `/emails/*` | `/api/v1/assistant/turns/stream` | `email-rag` Profile로 RAG 검색과 답변 실행 |
| Observer 조회 context | `/api/v1/assistant/turns/stream` | `observer-analysis` Profile로 현재 데이터를 재조회해 분석 |
| `/appstore` | `/api/v1/assistant/turns/stream` | `appstore-context` Profile로 현재 필터의 제한된 앱 카탈로그를 재조회 |
| `/ESOP_Dashboard/status/:lineId`, `/history/:lineId` | `/api/v1/assistant/turns/stream` | `line-dashboard-context` Profile로 line·기간별 상태/이력 snapshot 재조회 |
| 그 외 전역 ChatWidget, `/assistant` | `/api/v1/assistant/turns/stream` | `portal-default` Profile로 서버 memory를 사용해 실행 |

실행과 user/assistant 메시지 저장은 Turn endpoint만 담당합니다. 클라이언트가 별도 실행 이력이나 완료 메시지를 주입하는 API는 제공하지 않습니다.

### 표준 Turn API

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
  "profileVersion": 2,
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
| `portal-default` v2 | OpenWebUI | `shared` | `shared` | `assistant` |
| `email-rag` v2 | OpenWebUI + `rag.search` | `shared`, `scope:emails` | `scope:emails` | `assistant`, `emails` |
| `observer-analysis` v2 | `observer.analysis` 현재 데이터 재조회 | `shared`, `scope:observer` | `scope:observer` | `assistant`, `observer` |
| `appstore-context` v2 | OpenWebUI + `appstore.catalog` | `shared`, `scope:appstore` | `scope:appstore` | `assistant`, `appstore` |
| `line-dashboard-context` v2 | OpenWebUI + `line-dashboard.snapshot` | `shared`, `scope:line-dashboard` | `scope:line-dashboard` | `assistant`, `line-dashboard` |

`portal-default` v2는 `shared` partition만 읽고 기록합니다. 앱별 Profile의 scoped 메시지와 요약은 Provider에 전달하기 전에 저장 당시의 Account/data 권한을 현재 사용자 기준으로 다시 검증합니다.

#### 실행 유형과 재실행

`action`은 다음 값을 지원합니다.

| 값 | 동작 | 추가 필수 필드 |
| --- | --- | --- |
| `send` | 질문 전송 | 없음(기본 Turn 필드 사용) |
| `edit` | 질문 편집 | `targetMessageId` |
| `regenerate` | 답변 재생성 | `targetMessageId` |
| `retry` | 실행 재시도 | `retryRunId` |

모든 재실행은 새 `clientRequestId`와 user `clientId`를 사용합니다.
regenerate/retry는 저장된 Profile 버전과 제한된 Tool 입력을 재사용하지만 현재 Profile/Tool 권한 하한을 다시 적용합니다.

#### 화면 출처와 도구 입력

`appContextKey`는 prompt 출처이며 생략하거나 알 수 없는 앱으로 대신 실행할 수 없습니다. Portal은 `assistant:openwebui:<등록 앱>`, Email은 `assistant`, Observer는 현재 Tool 입력에서 계산한 `observer:v1:<sha256>`, Appstore는 `appstore:v1`, ESOP Dashboard는 `line-dashboard:v1`만 허용합니다. Appstore Tool 입력은 `query`, `category`, `selectedAppId`, ESOP Tool 입력은 `view`, `lineId`, `from`, `to`만 허용하며 서버가 다시 정규화합니다.

#### 스트리밍과 완료 결과 재전달

표준 SSE event는 `run.started`, `tool.started`, `tool.completed`, `run.heartbeat`, `message.delta`, `message.completed`, `run.completed`, `run.failed`입니다.

Portal 답변은 외부 OpenAI 호환 chunk가 도착하는 대로 `message.delta`로 전달합니다.
구조화 검증이 필요한 Email/Observer는 전체 JSON 검증을 통과한 뒤 표시 가능한 block을 전달합니다.

같은 `clientRequestId`와 동일 hash의 완료 Run은 현재 권한 재검증 뒤 저장된 `message.completed`만 replay합니다.
branch, 메시지, summary는 변경하지 않습니다. 다른 hash 또는 미완료 Run은 409입니다.

### RAG 인덱스 목록

```http
GET /api/v1/assistant/rag-indexes
```

응답에는 사용자가 선택할 수 있는 RAG index, 기본 index, Email scope에서 계산한 permission group이 포함됩니다. mailbox claim은 서버가 같은 Email scope에서 계산하므로 클라이언트가 제출하지 않습니다.

### 사용자별 대화방 저장

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

최근 10개를 제외한 같은 partition 메시지가 12개 이상 새로 쌓이면 다음 endpoint가 오래된 이력을 rolling summary로 갱신합니다. Portal, Email, Observer, Appstore, ESOP Dashboard partition은 서로 섞지 않습니다.

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

### Run 중복 방지와 종료 처리

Turn service가 `clientRequestId`와 요청 hash를 원자적으로 확인해 중복 실행을 막습니다. 완료·사용자 중단·요청 실패는 각각 `completed`, `stopped`, `failed`로 기록하고, 연결이 끊기거나 timeout이 발생하면 upstream response/session을 닫은 뒤 Run을 `stopped` 처리합니다. 완료 저장 직전에는 활성 Run, lease 만료, 예상 branch head를 다시 잠금 검증하므로 늦게 도착한 결과는 저장되지 않습니다. 브라우저가 별도 lease를 획득하거나 종료 상태를 보정하는 API는 없습니다.

### 대화 관리와 내보내기

- 대화방 PATCH는 `name`, `pinned`, `archived` 중 하나 이상을 받습니다.
- 답변 평가는 `rating: up|down`과 선택적 `reason`을 메시지별 하나만 저장합니다.
- `exportFormat=markdown`은 읽기용 문서, `exportFormat=csv`는 Excel 호환 UTF-8 BOM CSV를 반환합니다.
- CSV의 사용자 입력 셀은 `=`, `+`, `-`, `@` 등으로 시작할 때 Excel 수식으로 실행되지 않도록 텍스트 처리합니다.
- 수정·재생성으로 분기가 생긴 경우 내보내기와 rolling summary에는 현재 활성 분기만 사용합니다.

### 권한 규칙

Turn endpoint는 Django session과 Profile별 Account scope를 검사합니다. Appstore와 ESOP Dashboard snapshot은 각각 `appstore`, `line-dashboard` scope가 있어야 조회·저장·재사용할 수 있습니다. Email Tool의 permission group 선택·검색·저장·재검증은 모두 `emails` scope에서 서버가 계산한 접근 가능 그룹을 기준으로 합니다. `assistant` scope 소속은 Email 검색 범위를 넓히지 않습니다.

대화방 endpoint는 UUID만으로 접근할 수 없으며 항상 `conversation.user == request.user` 조건을 적용합니다. 다른 사용자의 방은 존재 여부를 노출하지 않고 404를 반환합니다.

Run, 메시지, 요약, 자동 제목은 version 1 `access_requirements`에 Account scope와 `ragPermissionGroups`/`mailboxes` data claim을 저장합니다. 조회·검색·내보내기·feedback·edit·regenerate·retry·replay마다 현재 권한을 다시 검사합니다. 하나라도 회수되면 답변 전체를 잠그고 내부 group/mailbox 이름은 반환하지 않습니다. 잠긴 메시지는 ID, role, 생성 시각, parent/revision/Run 관계만 반환하고 본문·block·source·context snapshot은 제외합니다. 내보내기는 일반 권한 제외 문구로 대체합니다.

legacy provenance는 `backfill_assistant_run_access --dry-run --batch-size N --checkpoint-file <path>`로 분류합니다. command는 재실행 가능하며 해석 불가능한 데이터는 `legacy-unresolved` synthetic Run에 연결해 계속 잠급니다.

서버가 기본으로 계산하는 그룹:

- Emails scope에서 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

### 오류

Turn 연결 전 검증 오류는 JSON HTTP 응답으로 반환합니다. SSE 연결 후 실행 오류는
HTTP 200 stream 안의 `run.failed` 등 종료 event로 전달되므로 HTTP status만으로 성공을 판단하지 않습니다.


| Status | 상황 |
| --- | --- |
| 400 | 필수 Turn 필드 누락, 형식 오류 |
| 401 | 로그인 필요 |
| 403 | permission group 접근 불가 또는 `knox_id` 없음 |
| 404 | 본인 소유가 아닌 대화방 또는 존재하지 않는 대화방 |
| 409 | 멱등성 충돌, 미완료 Run replay 또는 제목 생성에 필요한 대화 부족 |
| 502 | RAG 또는 OpenWebUI 호출 실패 |
| 503 | RAG 또는 OpenWebUI 설정 누락 |

### 관련 모듈 문서

- [Assistant / OpenWebUI / RAG 모듈](#기능과-흐름)
