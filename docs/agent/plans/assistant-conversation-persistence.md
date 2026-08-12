# ExecPlan: Assistant 사용자별 대화방 영구 저장

## 목표
- 로그인 사용자마다 대화방과 메시지를 DB에 분리 저장한다.
- 다른 브라우저나 PC에서도 같은 사용자의 대화방을 이어서 사용할 수 있게 한다.
- OpenWebUI, 메일 RAG, Observer는 현재 대화방 안에서도 같은 context의 최근 메시지만 모델 입력으로 사용한다.

## 현재 상태
- 프론트는 전체 대화방과 최근 메시지를 사용자 구분 없는 `localStorage`에 저장한다.
- backend cache는 `knox_id + roomId`로 분리되지만 최근 20개, 6시간 TTL의 임시 저장이다.
- 일반 OpenWebUI와 메일 RAG는 backend cache를 사용하고 Observer는 frontend가 전달하는 context history를 사용한다.

## 범위
- Assistant 도메인에 conversation/message 모델과 최초 migration을 추가한다.
- 본인 대화방 목록·생성·삭제, 방별 메시지 조회·추가 API를 추가한다.
- 프론트 `useChatSession`의 원본을 서버 API로 전환한다.
- Assistant에서는 `localStorage`를 사용하지 않고 활성 대화방은 서버 목록에서 결정한다.
- 기존 OpenWebUI/메일 RAG/Observer 응답 UI와 권한 정책은 유지한다.
- 자동 요약과 관리자용 대화 열람 기능은 추가하지 않는다.

## 설계
- `AssistantConversation`: UUID PK, user FK, title, created_at, updated_at.
- `AssistantMessage`: conversation FK, client_id, role, content, context_key, sources, user_sdwt_prod, created_at.
- `(conversation, client_id)` unique constraint로 저장 재시도를 멱등 처리한다.
- 모든 selector/service는 request user로 conversation 소유권을 제한한다.
- 방 목록은 metadata만 반환하고, 활성 방의 최근 20개 메시지만 별도 조회한다.
- 메시지 저장은 모델 호출 전 user 메시지, 성공 후 assistant 메시지 순으로 수행한다.
- 대화방 삭제는 FK cascade로 메시지를 함께 삭제한다.
- 재접속 시 서버가 반환한 최신 대화방을 선택하고 기존 브라우저 저장값은 읽거나 변경하지 않는다.

## 실행 단계
- [x] 모델, migration, selector/service와 테스트를 구현한다.
- [x] conversation/message API와 권한 테스트를 구현한다.
- [x] frontend API와 server-backed `useChatSession`을 구현한다.
- [x] ChatWidget과 `/assistant`에 사용자 식별·loading/error 상태를 연결한다.
- [x] 문서와 offsite dummy 호환성을 확인한다.
- [x] backend/frontend 테스트, migration check, build/lint, 경계/UI/docs 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant --noinput`
- `npm --prefix apps/web test -- --run`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build -- --outDir <temporary-directory>`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: 다른 사용자의 UUID를 추측해 대화를 조회할 수 있다.
- 대응: 모든 조회·삭제·메시지 추가에서 user 조건을 함께 적용하고 404로 응답한다.
- 위험: 모델 성공 후 메시지 저장이 실패하면 화면과 DB가 달라질 수 있다.
- 대응: user 메시지는 모델 호출 전에 저장하고 assistant 저장 실패는 명시적 오류로 표시한다.
- 위험: 여러 탭에서 같은 메시지를 재전송해 중복 저장될 수 있다.
- 대응: frontend client message ID와 DB unique constraint를 사용한다.
- 위험: 브라우저에 남아 있는 과거 Assistant 저장값이 계속 존재할 수 있다.
- 대응: 애플리케이션에서 `localStorage`를 읽거나 변경하지 않으며 서버 DB만 대화 원본으로 사용한다.

## 진행 기록
- 2026-08-11: 사용자 승인에 따라 사용자별·대화방별 DB 영구 저장 설계를 시작했다.
- 2026-08-11: 외부 OpenWebUI/RAG request contract와 env URL은 바뀌지 않아 `apps/adfs_dummy`, Compose, env 변경이 불필요함을 확인했다.
- 2026-08-11: DB history를 원본으로 사용하도록 chat endpoint가 6시간 cache보다 현재 request history를 우선하게 했다.
- 2026-08-11: Assistant backend 25개, Observer backend 7개, frontend 81개 테스트와 migration check, lint, 임시 경로 production build를 통과했다.
- 2026-08-11: frontend/backend 경계, UI 일관성, 문서 정합성 감사와 `git diff --check`를 통과했다.
- 2026-08-11: 기본 `apps/web/dist`는 기존 파일 소유권 때문에 정리할 수 없어, 새 임시 출력 경로에서 동일한 production build를 검증했다.
- 2026-08-11: 사용자 요청에 따라 활성 대화방과 RAG 설정을 포함한 Assistant의 모든 `localStorage` 사용을 제거했다.
