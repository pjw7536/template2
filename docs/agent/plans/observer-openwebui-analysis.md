# ExecPlan: Observer OpenWebUI 종합 분석

## 목표
- 사용자가 Observer 조회 조건을 기준으로 EQP/TIP 관심 상태와 주변 로그를 종합 분석한 결과를 확인할 수 있게 한다.
- 현재 운영 중인 `OPENWEBUI_*` 설정과 `gpt-oss-120b` Chat Completions endpoint를 그대로 사용한다.

## 현재 상태
- Observer는 최대 90일 범위의 EQP, TIP, SPC/FDC Interlock, CTTTM, RACB, ESOP 로그를 조회한다.
- EQP/TIP compact 목록에는 상태, 시간, comment preview가 있으며 전체 comment는 기존 selector에서 조회할 수 있다.
- CTTTM OpenWebUI 요약 배치는 `OPENWEBUI_URL`, `OPENWEBUI_MODEL`, `OPENWEBUI_API_TOKEN`, `OPENWEBUI_COMMON_HEADERS`, `OPENWEBUI_TIMEOUT_SECONDS`를 사용한다.
- `observer/selectors.py`와 `observer/tests.py`에는 Work Hub 관련 staged 변경이 있으므로 그대로 보존한다.

## 범위
- Observer 분석 요청 serializer, 통계/원인 컨텍스트 생성 service, OpenWebUI 호출 service, POST API와 테스트를 추가한다.
- 기존 전역 ChatWidget에 Observer 조회 context와 OpenWebUI 분석 결과 표시를 연결한다.
- Observer API/모듈 문서에 새 분석 계약을 기록한다.
- DB schema, migration, 기존 OpenWebUI 환경변수, 기존 CTTTM 요약 동작은 변경하지 않는다.

## 설계
- 프론트는 raw log 대신 `eqpId`, 조회 기간, 활성 log type, TIP group을 POST한다.
- 분석 대상 EQP 상태는 `DOWN`, `IDLE`, `LOCAL`이다.
- TIP은 `DOING`, `CNT`를 제외하고 대소문자 무시 `^L.*_TIP$`에 해당하는 상태만 대상으로 한다.
- EQP/TIP는 상태/공정/step/PPID와 정규화된 comment 기준 통계를 만들고, target event를 원인 탐색 anchor로 사용한다.
- SPC/FDC/CTTTM/RACB/ESOP는 target event 전 30분부터 후 10분까지 겹치는 raw context event만 포함한다.
- source별 최대 5,000건과 prompt 문자 예산을 적용하고 coverage에 truncation을 명시한다.
- OpenWebUI는 `reasoning_effort=medium`, `stream=false`, `tool_choice=none`으로 호출하며 JSON 응답을 검증한다.
- 권한은 기존 Observer의 전역 `app:observer` DRF permission을 그대로 사용한다.
- migration/env 변경은 없다.

## 실행 단계
- [x] 분석 request/response 계약과 통계 service 테스트를 추가한다.
- [x] Observer 분석 service와 OpenWebUI 호출을 구현한다.
- [x] POST `/api/v1/observer/analysis`를 연결한다.
- [x] 프론트 API/hook/분석 Dialog와 실행 버튼을 구현한다.
- [x] 문서를 갱신하고 테스트·audit을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --noinput`
- `npm --prefix apps/web test -- --run` 또는 저장소의 대응 frontend test 명령
- `npm run agent:audit:api-boundary`
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`

## 위험과 대응
- 위험: 많은 로그가 OpenWebUI context를 초과할 수 있다.
- 대응: 관심 상태 통계, 주변 raw event, source limit, prompt 문자 예산과 coverage를 사용한다.
- 위험: comment에 직접 기록된 원인과 시간상 인접한 추정 원인이 혼동될 수 있다.
- 대응: prompt와 응답 계약에서 `recordedCauses`와 `inferredCauses`를 분리하고 evidence ID를 요구한다.
- 위험: 조회 조건 변경 후 이전 분석이 노출될 수 있다.
- 대응: frontend mutation을 조회 key에 묶고 조건 변경 시 결과를 초기화한다.
- 위험: 현재 staged Observer 변경과 충돌할 수 있다.
- 대응: 기존 변경 인접 영역을 최소 수정하고 diff로 staged/unstaged 범위를 별도 확인한다.

## 진행 기록
- 2026-08-11: 사용자 합의에 따라 관심 상태, TIP 제외 규칙, 원인 탐색 범위, 기존 OpenWebUI 재사용을 확정했다.
- 2026-08-11: backend 분석/호출 service와 API, frontend 실행 버튼/Dialog, focused backend 테스트를 구현했다.
- 2026-08-11: EQP/TIP 관심 상태를 DB에서 선별하도록 보강하고 backend/frontend 회귀 테스트, lint/build, backend/frontend/UI/docs audit을 완료했다.
- 2026-08-11: local dev는 기존 offsite dummy OpenWebUI 설정(`dummy-model`)을 사용함을 확인했다. 배포 환경의 `OPENWEBUI_MODEL=gpt-oss-120b` 계약은 변경하지 않았다.

## 후속 전환: 기존 ChatWidget 재사용
- [x] 전역 route orchestration에 page assistant context provider를 추가한다.
- [x] ChatWidget이 page context별 message sender와 안내 상태를 지원하게 한다.
- [x] Observer 조회 조건과 OpenWebUI 분석 API를 page context로 등록한다.
- [x] Observer 전용 분석 버튼, mutation hook, 결과 Dialog를 제거한다.
- [x] frontend 테스트·lint·build·boundary/UI audit과 문서를 갱신한다.

### 전환 설계
- 이 후속 작업 당시 위젯의 일반 화면은 `/api/v1/assistant/chat`을 유지했으며, 이후 `assistant-openwebui-routing.md`에서 메일함 외 화면을 OpenWebUI로 전환했다.
- Observer context가 활성화되면 위젯 메시지는 `/api/v1/observer/analysis`로 보내고, backend가 기존 `OPENWEBUI_*` 설정을 사용한다.
- feature 간 직접 import를 만들지 않기 위해 `apps/web/src/lib/assistant`의 공용 page context만 공유한다.
- Observer context에서는 RAG 선택 UI 대신 연결된 EQP·조회 기간과 `현재 조회 데이터 종합 분석` 빠른 질문을 표시한다.
- 설비·기간·로그 유형·TIP group 변경 시 등록 context를 교체하며, 응답에는 분석 scope를 함께 표시한다.
- 기존 Assistant 권한에 따른 ChatWidget 노출 정책은 변경하지 않는다.

### 전환 진행 기록
- 2026-08-11: 공용 page context, context별 sender/history 분리, Observer markdown 변환과 위젯 연결 상태 UI를 구현했다.
- 2026-08-11: 기존 Observer 분석 버튼·Dialog를 제거하고 frontend 69건, Observer backend 7건, lint/build/frontend boundary/UI/docs audit을 완료했다.

## 후속 개선: 분석 중심 ChatWidget 출력

### 목표
- ChatWidget 본문에서는 기록된 원인, 근거 ID, 범위·입력·버전 같은 단순 정보를 반복하지 않고 데이터에서 도출한 핵심 분석만 표시한다.
- 범위·coverage·근거 이동 정보는 기존 `contextSnapshot`과 `분석 범위와 근거` 패널에 유지한다.

### 범위
- Observer 분석 system prompt와 기본 질문을 패턴·시간적 연관성·운영상 의미 중심으로 개선한다.
- Observer markdown formatter와 frontend/backend 회귀 테스트를 갱신한다.
- Observer API·모듈 문서를 실제 표시 정책에 맞춘다.
- DB schema, migration, auth/permission, env, 분석 대상 로그와 API 응답 필드는 변경하지 않는다.

### 설계
- `headline`, `summary`, 각 finding의 `assessment`는 사용자 표시용 분석으로 취급한다.
- `recordedCauses`, `inferredCauses`, `evidenceIds`는 모델 판단과 검증·근거 이동에 필요한 구조화 metadata로 유지하되 ChatWidget 본문에는 직접 표시하지 않는다.
- `recommendedChecks`는 기본 본문에서 제외하고, 결론의 신뢰성에 영향을 주는 `limitations`만 간결하게 표시한다.
- finding은 중요도 순 최대 5개로 제한하고 단순 건수 재진술 대신 반복·집중·선후 관계·상관성·운영상 의미를 설명하게 한다.
- API schema와 일반·stream prompt는 기존 `v1` 식별자를 유지하고 내용을 갱신한다.

### 실행 단계
- [x] 분석 system prompt와 기본 질문을 분석 중심으로 변경한다.
- [x] ChatWidget formatter에서 metadata와 단순 정보 섹션을 제거한다.
- [x] frontend/backend 테스트를 새 표시·프롬프트 정책에 맞춘다.
- [x] Observer API·모듈 문서를 갱신한다.
- [x] backend/frontend 회귀 테스트와 boundary/UI audit을 실행한다.

### 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web test -- --run src/features/observer/utils/observerAnalysisChat.test.js`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`

### 위험과 대응
- 위험: 본문에서 근거 ID를 제거하면 근거 탐색 기능이 사라질 수 있다.
- 대응: API 응답과 `contextSnapshot.evidenceTargets`는 유지하고 formatter 출력만 축약한다.
- 위험: 원인 목록을 숨긴 뒤 `assessment`가 빈도 재진술에 머물 수 있다.
- 대응: prompt에서 관찰·해석·확신 수준을 한 문단으로 종합하고 데이터로 도출되지 않은 일반론을 금지한다.

### 진행 기록
- 2026-08-12: API schema와 evidence snapshot을 유지하면서 ChatWidget 본문만 분석 중심으로 축약하기로 결정했다.
- 2026-08-12: 일반·stream prompt와 formatter를 분석 중심으로 통일하고 Observer backend 74건, frontend 전체 159건, lint, 임시 경로 production build, migration 무변경, backend/frontend/UI audit 통과를 확인했다. 기본 `apps/web/dist`는 기존 root 소유 asset 때문에 정리할 수 없어 임시 출력 경로에서 build를 검증했다.

## 후속 개선: CTTTM 시간순 요약 배경지식

### 목표
- Observer 분석에서 CTTTM `ct_process_comment.llm_summary`의 시간순 이벤트 정리를 배경지식으로 사용한다.
- CTTTM 핵심요약과 시간순 요약을 서로 덮어쓰지 않고 각각의 의미를 모델에 전달한다.

### 현재 상태
- CTTTM selector는 `llm_core_summary`와 `llm_summary`를 각각 `coreSummary`, `summary`로 이미 반환한다.
- 분석 context 변환은 `coreSummary || summary` 하나만 `summary` column에 넣으므로 두 값이 함께 있으면 `llm_summary`가 제외된다.

### 범위
- Observer 분석 context column과 일반·stream system prompt, service 테스트를 갱신한다.
- Observer API·모듈 문서에 CTTTM 배경지식 의미를 기록한다.
- CTTTM selector, DB schema, migration, 요약 생성 배치, auth/env 계약은 변경하지 않는다.

### 설계
- CTTTM context row의 `summary`는 `llm_core_summary`, `chronologicalSummary`는 `llm_summary`로 분리한다.
- 다른 로그 유형의 기존 `summary` 의미와 동작은 유지한다.
- 모델은 `chronologicalSummary`를 이벤트 흐름 해석의 배경지식으로 사용하되 독립된 raw 근거나 확정 원인으로 간주하지 않는다.
- context schema와 일반·stream prompt 내용은 변경하되 기존 `v1` 식별자를 유지한다.

### 실행 단계
- [x] CTTTM context row에 `chronologicalSummary`를 추가한다.
- [x] 일반·stream prompt에 시간순 요약 사용 규칙을 추가하고 버전을 갱신한다.
- [x] service 회귀 테스트와 Observer 문서를 갱신한다.
- [x] backend 테스트, migration 무변경, boundary audit을 실행한다.

### 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `git diff --check`

### 위험과 대응
- 위험: LLM 생성 요약이 원천 로그와 같은 수준의 확정 근거로 해석될 수 있다.
- 대응: system prompt에서 시간순 요약은 배경지식이며 event ID가 있는 raw context를 근거로 판단하도록 제한한다.
- 위험: context 크기가 증가해 주변 이벤트가 더 많이 축소될 수 있다.
- 대응: 기존 field별 1,000자 제한과 전체 prompt budget 축소 정책을 그대로 적용한다.

### 진행 기록
- 2026-08-12: 이미 조회 중인 `llm_summary`를 별도 context column으로 보존하고 배경지식 의미를 prompt에 명시하기로 결정했다.
- 2026-08-12: CTTTM 핵심요약과 시간순 요약을 분리하고 기존 schema/prompt `v1` 내용을 갱신했으며 Observer backend 75건, migration 무변경, backend boundary audit, diff 무결성 검증을 통과했다.
