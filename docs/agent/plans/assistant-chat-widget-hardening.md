# ExecPlan: Chat Widget 전면 개선

## 목표
- OpenWebUI 답변을 SSE로 스트리밍하고 사용자가 진행 중 응답을 중지할 수 있게 한다.
- 한 사용자당 하나의 생성 요청만 허용하되 생성 중에도 다른 대화방을 탐색할 수 있게 한다.
- Observer 조회 조건 변경을 같은 방의 명시적 구분선으로 표시하고 모델 문맥을 현재 조건으로 분리한다.
- 오래된 메시지와 대화방을 cursor 기반으로 탐색하고 장기 대화 요약을 모델 문맥에 포함한다.
- 실패 재시도, 공급자별 상태 문구, 삭제 확인과 Chat Widget 회귀 테스트를 추가한다.

## 현재 상태
- 일반 화면은 `/api/v1/assistant/openwebui-chat`의 JSON 완료 응답을 사용하고 최대 130초를 기다린다.
- `useChatSession`의 단일 mutation 상태가 입력과 대화방 목록을 모두 잠근다.
- 대화방과 메시지는 DB에 저장하지만 프론트엔드는 최근 20개 메시지만 불러온다.
- Observer는 같은 방에 메시지를 표시하면서 현재 `contextKey` 이력만 분석 요청에 전달한다.
- 저장소에는 기존 Assistant/Observer 변경이 커밋되지 않은 상태이므로 관련 변경을 보존하며 증분 수정한다.

## 범위
- 수정: `apps/api/api/assistant`, `apps/web/src/features/assistant`, Observer assistant context, Assistant 관련 문서와 테스트.
- 제외: 모바일 레이아웃 및 접근성 전용 개선, 인증/권한 정책 변경, 메일 RAG 응답의 SSE 전환.

## 설계
- 일반 OpenWebUI endpoint는 JSON 계약을 유지하고, 별도 `/openwebui-chat/stream` SSE endpoint를 추가한다.
- SSE event는 `meta`, `delta`, `done`, `error`로 구성하며 프론트엔드는 `fetch` stream을 직접 파싱한다.
- 브라우저 `AbortController`와 Django streaming iterator 종료를 연결해 중지한다.
- 생성 상태는 `activeGenerationRoomId`로 추적하고 다른 방 탐색은 허용하되 추가 전송은 전역 1개로 제한한다.
- 대화방 목록은 `search`, `cursor`, `limit`, 메시지는 `before`, `limit` cursor 계약을 사용한다.
- `AssistantConversation`에 rolling summary와 요약 기준 메시지 수를 저장하고, 일정 메시지 증가 시 OpenWebUI 저비용 요청으로 갱신한다.
- Observer scope 변경 메시지는 로컬/DB에 system 역할 대신 Assistant의 context-divider metadata로 저장하지 않고 UI 파생 구분선으로 표시한다.
- 삭제는 기존 Dialog primitive로 확인 후 실행하며 실패한 마지막 질문은 동일 방에서 재시도한다.

## 실행 단계
- [x] SSE service/view/API client와 스트리밍·중지 테스트를 추가한다.
- [x] 대화방별 생성 상태, 실패 재시도, 공급자별 상태 문구를 구현한다.
- [x] 대화방/메시지 cursor pagination과 검색 UI를 구현한다.
- [x] DB rolling summary migration/service와 모델 문맥 연결을 구현한다.
- [x] Observer 조회 조건 변경 구분과 후속 질문 문맥을 개선한다.
- [x] 삭제 확인 Dialog와 Chat Widget 상호작용 테스트를 추가한다.
- [x] API/프론트엔드 테스트, migration check, lint/build, 경계/UI 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check`
- `npm run test:run`, `npm run lint`, `npm run build` (`apps/web`)
- `npm run agent:audit:api-boundary`, `npm run agent:audit:web-boundary`, `npm run agent:audit:ui`
- corporate network 없이 mock된 OpenWebUI stream parser/service 테스트가 통과해야 한다.

## 위험과 대응
- 위험: 스트리밍 중 연결 종료가 upstream socket에 늦게 전달될 수 있다.
- 대응: iterator `finally`에서 response/session을 닫고 클라이언트는 즉시 UI 생성을 종료한다.
- 위험: 요약 생성 실패가 정상 채팅 저장을 방해할 수 있다.
- 대응: 요약은 best-effort 후처리로 격리하고 기존 최근 이력 fallback을 유지한다.
- 위험: cursor 계약 추가가 기존 호출을 깨뜨릴 수 있다.
- 대응: cursor 없는 기존 요청과 `results` 필드를 그대로 지원한다.

## 진행 기록
- 2026-08-11: 사용자가 SSE, 같은 방 scope 구분, cursor+rolling summary, 사용자당 동시 요청 1개 권장안을 승인했다.
- 2026-08-11: SSE·중단, 방 탐색 분리, 검색/과거 page, 재시도·삭제 확인과 상호작용 테스트를 구현했다.
- 2026-08-11: rolling summary를 contextKey별로 격리해 Observer 조회 조건과 일반/메일 문맥이 섞이지 않게 보완했다.
- 2026-08-11: Assistant 36개·Observer 65개 backend 테스트, frontend 104개 테스트, lint/build, migration check/apply, Nginx 설정, API/web/UI/docs 감사를 모두 통과했다.
