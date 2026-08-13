# ExecPlan: Email RAG OpenWebUI 전환

## 목표
- Email RAG의 검색·권한·출처·구조화 응답 계약은 유지한다.
- 검색 결과의 답변 생성 Provider만 기존 Assistant LLM 연결에서 `OPENWEBUI_*` 연결로 전환한다.

## 현재 상태
- `AssistantRuntime`의 `email-rag` Profile은 `AssistantChatService`로 RAG 검색과 답변 생성을 수행한다.
- Email 답변 생성 transport는 `AssistantChatConfig`의 `ASSISTANT_LLM_*` 연결 설정을 사용한다.
- 일반 Assistant, 제목, 장기 요약은 `AssistantOpenWebUIConfig`의 `OPENWEBUI_*` 연결 설정을 사용한다.
- 로컬 `adfs_dummy`는 Email 구조화 응답을 포함한 OpenAI 호환 streaming endpoint를 이미 제공한다.

## 범위
- Email 답변 생성 transport와 설정 로딩을 `OPENWEBUI_*`로 통합한다.
- 관련 backend 테스트, dev/common env, 설정 문서를 동기화한다.
- RAG 검색 endpoint, permission group/mailbox 필터, 응답 serializer/SSE 계약은 수정하지 않는다.
- DB schema, migration, frontend는 수정하지 않는다.

## 설계
- Email 전용 RAG·구조화 prompt 구성은 기존 `AssistantChatConfig`와 parser를 유지한다.
- 실제 OpenAI 호환 호출의 URL/model/token/common headers/timeout은 `AssistantOpenWebUIConfig`에서 읽는다.
- 인증 header는 기존 OpenWebUI와 같은 Bearer token 규칙을 공유한다.
- `ASSISTANT_LLM_TEMPERATURE`와 `ASSISTANT_LLM_SYSTEM_MESSAGE`는 Email RAG prompt 조정값으로 유지한다. `ASSISTANT_REQUEST_TIMEOUT`은 기존 RAG 검색 timeout으로 유지하고, 기존 `ASSISTANT_LLM_URL`, credential, model, headers 연결 계약만 제거한다.
- 로컬 dummy endpoint 형상은 이미 호환되므로 handler 변경 없이 dev env의 중복 URL만 제거한다.

## 실행 단계
- [x] Email 구조화 답변 transport를 OpenWebUI 설정으로 전환한다.
- [x] 기존 OpenWebUI header 구성을 공유하고 회귀 테스트를 추가한다.
- [x] env·legacy env migration 목록·통합 문서를 새 설정 계약과 동기화한다.
- [x] Docker Compose `api` 컨테이너에서 Assistant 테스트와 backend boundary audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant`
- `npm run agent:audit:api-boundary`
- 기대 결과: Email RAG 테스트가 OpenWebUI URL/model/Bearer/common headers/timeout 사용을 검증하고 전체 Assistant 테스트가 통과한다.

## 위험과 대응
- 위험: OpenWebUI 응답이 기존 Email JSON 계약을 지키지 않을 수 있다.
- 대응: 기존 구조화 system prompt와 엄격한 `answer`/`segments` parser를 유지하고 dummy/test로 계약을 검증한다.
- 위험: token이 없는 OpenWebUI 배포에서 기존 필수 credential 검증이 호출을 막을 수 있다.
- 대응: OpenWebUI 공통 동작처럼 token은 선택값으로 처리하고 설정된 경우에만 Bearer header를 보낸다.

## 진행 기록
- 2026-08-13: 기존 RAG/권한/출처 계약을 유지하고 답변 생성 연결만 OpenWebUI로 통합하기로 결정했다.
- 2026-08-13: dev dummy의 `/v1/chat/completions`가 Email 구조화 streaming 응답을 이미 지원해 mock handler 변경은 불필요함을 확인했다.
- 2026-08-13: `api.assistant` 테스트 44개, backend boundary audit, docs inventory audit가 통과했다.
- 2026-08-13: 실행 중인 dev Compose에서 실제 dummy RAG 검색 후 OpenWebUI 호환 stream 호출까지 성공했다.
