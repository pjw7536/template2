# ExecPlan: 화면별 Assistant OpenWebUI 전환

## 목표
- 메일함을 제외한 모든 화면의 기존 챗봇 위젯과 `/assistant` 전체 화면이 기존 `OPENWEBUI_*` 설정을 사용한다.
- `/emails/*` 화면의 챗봇은 현재 RAG 검색과 메일 출처 표시 흐름을 유지한다.
- Observer는 현재 조회 데이터를 구조화하는 전용 분석 API를 계속 사용한다.

## 현재 상태
- 일반 챗봇은 `/api/v1/assistant/chat`에서 RAG 검색 후 `ASSISTANT_LLM_*` 설정으로 답변을 생성한다.
- Observer는 `/api/v1/observer/analysis`에서 구조화된 조회 데이터를 `OPENWEBUI_*` endpoint로 전달한다.
- 전역 `ChatWidget`은 route와 무관하게 기본 Assistant sender를 사용하고, page context가 있으면 전용 sender로 교체한다.

## 범위
- Assistant backend에 일반 대화용 OpenWebUI endpoint와 transport를 추가한다.
- 전역 챗봇은 `/emails/*`에서만 기존 RAG sender를 사용하고, 나머지는 OpenWebUI sender를 사용한다.
- `/assistant` 전체 화면의 RAG 설정 UI를 제거하고 OpenWebUI sender를 사용한다.
- Assistant API/모듈/설정 문서를 갱신한다.
- Observer의 구조화 분석 로직과 메일 RAG API 내부 동작은 수정하지 않는다.

## 설계
- `/api/v1/assistant/openwebui-chat`은 `prompt`, `history`, `roomId`를 받고 OpenAI 호환 Chat Completions 응답을 기존 `{reply, sources, segments, meta, echo}` 형태로 정규화한다.
- 기존 `/api/v1/assistant/chat`은 메일함 전용 RAG/LLM 경로로 그대로 보존한다.
- frontend는 `location.pathname`이 `/emails` 또는 `/emails/*`인지 판단해 sender와 context key를 선택한다.
- Observer page context sender가 있으면 route 기본 sender보다 우선한다.
- DB, migration, auth, 새 env는 변경하지 않는다. 기존 session 인증과 Assistant 접근 권한을 재사용한다.

## 실행 단계
- [x] 현재 Assistant/OpenWebUI·메일 route 계약과 미커밋 변경 범위를 확인한다.
- [x] OpenWebUI 일반 채팅 API와 테스트를 추가한다.
- [x] 챗봇 위젯과 `/assistant` 화면을 route별 sender와 UI에 연결한다.
- [x] 문서와 오프사이트 더미 호환성을 확인한다.
- [x] backend/frontend 테스트, build, lint, 경계/UI/docs 감사를 실행한다.

## 검증
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
- 위험: 메일 RAG 대화와 일반 OpenWebUI 대화가 같은 room history에 섞일 수 있다.
- 대응: frontend context key와 backend cache namespace를 분리한다.
- 위험: generic OpenWebUI 전환으로 RAG 설정이 보이지만 사용되지 않을 수 있다.
- 대응: 메일 route에서만 RAG 설정 UI를 노출한다.
- 위험: corporate OpenWebUI 없이 오프사이트 개발이 중단될 수 있다.
- 대응: 기존 `env/api.local.env`의 OpenWebUI URL/model과 `apps/adfs_dummy`의 OpenAI 호환 endpoint를 그대로 사용한다.

## 진행 기록
- 2026-08-11: 메일 route만 기존 RAG 흐름을 유지하고 별도 OpenWebUI endpoint를 추가하는 설계로 확정했다.
- 2026-08-11: `env/api.local.env`의 `OPENWEBUI_URL`/`OPENWEBUI_MODEL`이 `apps/adfs_dummy`의 OpenAI 호환 `/v1/chat/completions`와 일치해 mock/env 변경이 불필요함을 확인했다.
- 2026-08-11: Assistant backend 22개, Observer 분석 backend 7개, frontend 78개 테스트와 lint/build, frontend/backend 경계, UI 일관성, docs inventory, diff 검증이 모두 통과했다.
