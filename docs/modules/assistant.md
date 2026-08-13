# Assistant / OpenWebUI / RAG 모듈

Assistant는 메일함 외 화면의 일반 질문을 OpenWebUI로 전달하고, 메일함에서는 RAG 검색과 기존 LLM을 조합해 근거가 있는 답변을 생성합니다. RAG app은 외부 RAG 서버를 호출하는 공통 client입니다.

## 기능 요약

- 사용 가능한 RAG index 조회
- permission group 검증
- 메일함 RAG 검색과 LLM 호출
- 일반 화면 OpenWebUI 대화
- 답변/출처/segment 반환
- 사용자/대화방 UUID 단위 DB 대화 이력 관리
- OpenWebUI 기반 업무용 대화방 제목 자동 생성
- SSE 답변 표시·중단·실패 재시도
- cursor 기반 대화방 검색·과거 메시지 조회와 모든 Portal 앱의 방 단위 공유 장기 요약
- 서버 generation lease 기반 다중 탭 중복 방지
- 질문 편집·답변 재생성 분기, 메시지 복사·평가
- 대화방 이름 변경·고정·보관, 현재 목록 전체 선택 삭제와 제목·본문 통합 검색
- Observer 범위·coverage·분석 버전·이동 가능한 근거 snapshot 표시와 Markdown·CSV 내보내기

## 권한 기준

Assistant는 다음 값을 permission group으로 사용합니다.

- 접근 가능한 `user_sdwt_prod`
- 사용자의 `knox_id`
- `rag-public`

요청 permission group이 이 범위를 벗어나면 거부합니다.

## 일반 화면 OpenWebUI 흐름

1. 전역 ChatWidget이 현재 route를 확인합니다.
2. `/emails/*`와 Observer page context가 아니면 현재 route를 허용된 `appKey`로 해석하고 `/api/v1/assistant/openwebui-chat/stream`으로 질문과 같은 방의 공유 대화 이력을 보냅니다.
3. 서버가 로그인 사용자와 `knox_id`를 확인합니다.
4. 현재 대화방의 `chatwidget:shared` 최근 이력을 사용하며 이전 메시지에는 생성된 앱 출처를 표시합니다.
5. 서버 허용 카탈로그의 현재 앱 배경지식, 같은 방의 공유 저장 요약과 최근 이력을 합쳐 기존 `OPENWEBUI_*` 설정으로 OpenAI 호환 Chat Completions를 호출합니다.
6. `meta`, `delta`, `done`, `error` SSE event로 답변을 표시하고 중단 시 upstream 연결을 닫습니다.

`/assistant` 전체 화면도 같은 OpenWebUI sender를 사용합니다. 일반 화면에서는 사용하지 않는 RAG index 조회와 설정 UI를 표시하지 않습니다.

## 메일함 RAG 흐름

1. `/emails/*` 화면에서 사용자가 `prompt`를 보냅니다.
2. 서버가 사용자와 `knox_id`를 확인합니다.
3. permission group과 RAG index를 검증합니다.
4. 현재 대화방의 Portal 공용 이력을 가져오되 이전 메시지에는 앱 출처를 표시합니다.
5. RAG 검색을 수행합니다.
6. 검색 결과를 LLM에 전달합니다.
7. 답변, 출처, segment, meta를 반환합니다.

## RAG client 역할

- RAG 검색
- Email 문서 insert
- 문서 delete
- index/permission group 정규화
- 실패 로그 기록

## 대화방 영구 저장

- `AssistantConversation`은 UUID와 user FK로 대화방 소유자를 고정합니다.
- `AssistantMessage`는 user/assistant role, 표시 content, context key, 출처와 parent/revision 관계를 저장합니다.
- `AssistantConversation.current_message`에서 parent를 따라간 경로가 현재 대화 분기이며 수정·재생성 전 원본도 DB에 보존합니다.
- `AssistantGeneration`은 사용자당 활성 생성 하나만 허용하고 180초 lease와 완료·중단·실패 상태를 기록합니다.
- `AssistantContextSnapshot`은 Observer 원본 행 대신 범위·coverage·분석 버전·근거 ID와 범위 복원 URL만 제한해 저장하고 `AssistantMessageFeedback`은 답변별 평가를 저장합니다.
- Observer 근거 패널은 분석 당시 범위와 현재 조회 범위가 같은지 표시하며, 근거 버튼으로 당시 조건을 복원한 Observer Data Log로 이동합니다.
- 방 목록은 검색 가능한 cursor page로 조회하고 활성 방의 최근 20개 메시지를 먼저 표시한 뒤 과거 page를 앞에 추가합니다.
- 모델 호출 전 user 메시지, 성공 후 assistant 메시지를 저장합니다.
- frontend는 서버 DB와 React Query를 원본으로 사용하며 `localStorage`를 사용하지 않습니다.
- 재접속 시 서버가 반환한 최신 대화방을 활성화하고, 메일 RAG 선택값은 현재 실행 중인 메모리에서만 유지합니다.
- backend 6시간 cache는 호환용 보조 저장이고, 모델 입력은 frontend가 현재 DB 방에서 불러온 history를 우선합니다.
- 최근 10개 메시지는 그대로 유지하고 충분히 누적된 과거 메시지는 OpenWebUI 저비용 요청으로 최대 2,000자의 rolling summary를 만듭니다.
- 같은 대화방의 일반 앱(`assistant:openwebui:<appKey>`), Observer(`observer:*`), Email RAG(`assistant`)는 `chatwidget:shared` 기억 그룹으로 최근 이력과 rolling summary를 공유합니다. `contextKey`는 기억을 분리하지 않고 요청 sender·메시지 앱 출처·현재 Observer 조회 범위를 구분합니다.
- 앱을 이동하면 대화방과 기억은 유지하고 현재 앱의 sender·고정 배경지식·화면 데이터만 교체합니다. 기존 `assistant:openwebui` 메시지는 Portal 출처로 계속 해석합니다.
- Observer 분석에서는 공유 대화와 장기 요약을 질문 의도·용어·후속 질문을 이해하는 배경으로만 사용하고, 사실 판단은 현재 조회 조건의 `observer_analysis_context_json`만 근거로 삼습니다.
- 새로고침·탭 종료 시 현재 generation을 실패 처리하며, 연결이 끊긴 답변을 백그라운드에서 계속 생성하거나 SSE에 재연결하지 않습니다.
- 대화방 선택 모드는 현재 검색·보관 조건에서 불러온 방을 대상으로 하며, 생성 중인 방을 제외하고 기존 소유자 전용 DELETE API로 삭제합니다. 일부 요청이 실패하면 성공한 방만 제거하고 실패한 방은 재시도할 수 있게 남깁니다.
- 최초 `무엇을 도와드릴까요?` 인사에는 메시지 action을 표시하지 않습니다.
- ChatWidget의 대화방 메뉴·Dialog 같은 portal이 열려 있을 때 바깥 클릭은 portal만 닫고 ChatWidget 자체는 유지합니다.

## 대화방 제목 자동 생성

1. frontend가 첫 user 메시지와 Assistant 답변을 DB에 저장합니다.
2. 답변 저장 성공 후 `/conversations/<uuid>/generate-title`을 비동기로 호출합니다.
3. backend가 본인 소유 방인지 확인하고 저장된 최근 메시지를 조회합니다.
4. `새 대화` 계열 이름일 때만 기존 OpenWebUI 설정으로 제목을 요청합니다.
5. Markdown, 따옴표, 접두어와 종결 문장부호를 제거하고 최대 40자로 저장합니다.
6. frontend가 React Query 대화방 cache를 갱신해 목록에 즉시 반영합니다.

제목 형식은 핵심 주제 중심의 한국어 명사형 2~7어절입니다. 장비명, `DOWN`, `IDLE`, `L*_TIP` 같은 상태명과 기술 용어는 원문을 유지합니다. 제목 요청은 채팅 전송 상태와 분리하므로 실패하거나 지연되어도 답변 표시와 다음 질문을 막지 않습니다.

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/assistant` |
| Frontend | `apps/web/src/features/assistant` |
| Backend API | `/api/v1/assistant/rag-indexes`, `/api/v1/assistant/chat`, `/api/v1/assistant/openwebui-chat/stream`, `/api/v1/assistant/conversations*` |
| 데이터 | Account 권한 그룹, `assistant_conversation`, `assistant_conversation_summary`, `assistant_message`, `assistant_generation`, `assistant_context_snapshot`, `assistant_message_feedback` |
| 외부 연동 | OpenWebUI 일반 대화 SSE·대화방 제목·장기 요약 chat completions, RAG search, 기존 Assistant LLM chat completions |

## 운영 포인트

- 답변이 빈 경우 RAG index, permission group, RAG 검색 결과를 먼저 확인합니다.
- 일반 화면의 502/503은 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, token/header, timeout 설정을 확인합니다.
- 메일함의 403은 요청 permission group이 서버 계산 그룹을 벗어났거나 `knox_id`가 없을 때 발생할 수 있습니다.
- 메일함의 502/503은 RAG/LLM URL, header, timeout 설정을 확인합니다.

## 관련 API

- `docs/api/assistant.md`

## 관련 코드

- `apps/api/api/assistant/views.py`
- `apps/api/api/assistant/services/chat.py`
- `apps/api/api/assistant/services/config.py`
- `apps/api/api/assistant/services/conversations.py`
- `apps/api/api/assistant/services/generations.py`
- `apps/api/api/assistant/services/exports.py`
- `apps/api/api/assistant/services/memory.py`
- `apps/api/api/assistant/services/normalization.py`
- `apps/api/api/assistant/services/openwebui.py`
- `apps/api/api/assistant/services/reply.py`
- `apps/api/api/rag/services/client.py`
- `apps/api/api/rag/services/config.py`
- `apps/web/src/features/assistant`
