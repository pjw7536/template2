# ExecPlan: OpenWebUI 대화방 제목 자동 생성

## 목표
- 첫 질문과 답변이 저장된 뒤 OpenWebUI가 업무용 대화 제목을 생성한다.
- 생성된 제목을 사용자 소유 대화방에 저장하고 Chat Widget 목록에 즉시 반영한다.
- 제목 생성 실패나 지연이 채팅 답변 표시와 다음 메시지 입력을 막지 않게 한다.

## 현재 상태
- 대화방은 `AssistantConversation.title`에 이름을 저장하고 기본값은 `새 대화` 계열이다.
- 일반 화면, Observer 분석은 기존 OpenWebUI 설정을 사용하고 메일함은 RAG 채팅을 사용한다.
- frontend는 질문과 답변을 DB에 저장하지만 대화방 제목을 갱신하는 API는 없다.

## 범위
- 기존 OpenWebUI Chat Completions 연결을 재사용한 제목 생성 서비스를 추가한다.
- 사용자 소유 대화방의 제목 생성 endpoint를 추가한다.
- 첫 답변 저장 후 제목 생성을 비동기로 요청하고 대화방 목록 cache를 갱신한다.
- API·모듈·연동 문서와 backend/frontend 테스트를 갱신한다.
- 수동 이름 편집 UI, 제목 재생성 버튼, DB schema 변경은 추가하지 않는다.

## 설계
- 제목은 핵심 주제 중심의 한국어 명사형 2~7어절, 최대 40자로 요청한다.
- 따옴표, Markdown, 이모지, 문장부호, `제목:` 접두어를 서버에서 제거한다.
- `새 대화` 또는 `새 대화 N`인 방만 생성하며 이미 제목이 있는 방은 그대로 반환한다.
- endpoint는 저장된 최근 메시지를 사용하고 사용자 소유권을 UUID와 함께 검사한다.
- frontend는 답변 메시지 저장 성공 후 제목 생성을 fire-and-forget으로 요청한다.
- 기존 `OPENWEBUI_*` env, 모델, 인증 header와 offsite OpenAI 호환 dummy endpoint를 그대로 사용한다.
- 기존 `title` 컬럼을 사용하므로 migration은 없다.

## 실행 단계
- [x] OpenWebUI 제목 prompt·정규화·대화방 갱신 서비스를 구현한다.
- [x] 제목 생성 API와 소유권·실패 격리 테스트를 구현한다.
- [x] frontend API와 `useChatSession` 비동기 제목 갱신을 구현한다.
- [x] 문서와 offsite 계약 정합성을 갱신한다.
- [x] backend/frontend 테스트, migration check, lint/build, 경계·문서 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web run test:run`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build -- --outDir <temporary-directory>`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: 제목 생성 요청이 긴 OpenWebUI 응답 시간만큼 채팅을 막을 수 있다.
- 대응: 답변 저장 이후 비동기로 호출하고 `isSending` 상태에 포함하지 않는다.
- 위험: 모델이 설명이나 Markdown을 포함한 제목을 반환할 수 있다.
- 대응: 서버 정규화와 최대 40자 제한을 적용하고 유효하지 않으면 기본 이름을 유지한다.
- 위험: 다른 사용자의 UUID로 제목을 변경할 수 있다.
- 대응: 기존 사용자 조건 selector로 소유권을 확인하고 동일한 404를 반환한다.
- 위험: 여러 탭이 같은 기본 방의 제목을 동시에 요청할 수 있다.
- 대응: backend는 기본 이름일 때만 갱신하고 frontend는 방별 진행 요청을 중복 방지한다.
- 대응: 외부 호출 이후에도 DB 제목이 기존 기본값일 때만 조건부 UPDATE해 삭제된 방 재생성과 동시 요청 덮어쓰기를 막는다.

## 진행 기록
- 2026-08-11: 기존 OpenWebUI 설정과 `AssistantConversation.title`을 재사용하는 설계를 확정했다.
- 2026-08-11: 외부 endpoint/request schema와 env는 바뀌지 않아 offsite dummy·Compose 변경이 불필요함을 확인했다.
- 2026-08-11: 기본 이름 판별, 제목 전용 prompt, 40자 정규화와 비동기 frontend 반영을 구현했다.
- 2026-08-11: 제목 생성 중 삭제·동시 변경 경쟁 조건을 조건부 UPDATE로 차단했다.
- 2026-08-11: Assistant backend 30개와 frontend 87개 테스트, migration check, lint, production build를 통과했다.
- 2026-08-11: backend/frontend 경계와 문서 정합성 감사, `git diff --check`를 통과했다.
