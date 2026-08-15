# ExecPlan: Assistant 앱 지식 자동 라우팅

## 목표
- ChatWidget의 지식 스위치가 켜져 있어도 사용자 질문과 최근 대화를 먼저 해석하고, 앱 지식이 필요한 경우에만 동적 도구를 실행한다.
- 일반 질문은 앱 snapshot·로그 분석·메일 검색 결과의 제약을 받지 않고 일반 Assistant 답변을 생성한다.
- ChatWidget의 지식 모드를 `현재 앱 지식만 사용`과 `자동 지식 선택`으로 분리한다.
- 현재 앱 전용 모드는 다른 앱으로 전환하지 않고, 자동 모드에서만 권한이 확인된 앱 지식을 선택한다.

## 변경 전 상태
- `apps/web/src/features/assistant/utils/surfaceConfig.js`는 Emails 앱에서 지식 사용이 켜지면 모든 질문을 `email-rag` Profile로 보냈다.
- `apps/api/api/assistant/services/chat.py`는 실제 Provider 요청 전에 항상 RAG 문서를 조회했다.
- RAG 문서가 하나라도 있으면 `apps/api/api/assistant/services/llm.py`가 일반지식 사용을 금지했다.
- Appstore·Line Dashboard·Observer는 전용 Profile이 선택되면 프롬프트와 무관하게 snapshot 또는 로그 분석을 실행했다.

## 범위
- Email RAG와 Appstore·Line Dashboard·Observer 도구를 질문 의도에 따라 조건부 실행한다.
- 모든 ChatWidget 앱의 스위치 문구를 자동 사용 의미로 명확히 한다.
- 조회 도구가 없는 앱의 고정 설명은 질문과 관련 있을 때만 참고하도록 prompt를 제한한다.
- Assistant backend와 frontend 회귀 테스트를 추가한다.
- 자동 모드에서 Email·Observer·Appstore·Line Dashboard 중 하나를 선택하는 상위 라우터를 추가한다.
- Observer·Line Dashboard 필수 조회 범위가 없는 교차 앱 요청은 도구 호출 없이 명확화 질문을 반환한다.

## 설계
- 기존 `email-rag` v1은 항상 RAG를 조회하는 의미로 보존하고, 자동 판별은 v2로 추가한다.
- 기존 Appstore·Line Dashboard·Observer v1은 항상 도구를 실행하고, 자동 판별은 각 v2에 추가한다.
- Email Provider가 현재 질문과 서버가 구성한 최근 대화 문맥을 판별 모델에 전달한다.
- 다른 동적 앱도 같은 판별 transport를 사용하되 앱별 도구 목적을 system policy로 제공한다.
- 판별 결과는 `useKnowledge`와 `searchQuery`만 허용하며, 메일 사실 조회·검색·요약·후속 질문일 때만 RAG를 실행한다.
- 판별 실패 또는 형식 오류 시 기존 RAG 실행으로 복귀해 메일 질문을 놓치지 않는다.
- 일반 질문에서는 `rag.search` tool 기록과 RAG permission group data claim을 남기지 않는다.
- 다른 앱의 일반 질문에서도 selector/분석 호출과 tool key, context snapshot을 남기지 않는다.
- Assistant dummy mode에서는 별도 판별 외부 호출을 만들지 않고, `ASSISTANT_DUMMY_USE_RAG`가 허용된 경우 결정적 로컬 규칙으로 자동 사용을 재현한다.
- offsite OpenWebUI dummy endpoint는 공통 판별 JSON 계약을 결정적으로 재현한다.
- 외부 RAG HTTP schema, DB schema, auth/permission 하한, env 설정은 변경하지 않는다. Migration은 필요 없다.
- 기존 앱별 Profile v1/v2는 replay와 현재 앱 전용 모드에 유지하고, 자동 선택은 별도 `auto-knowledge` Profile로 분리한다.
- 자동 Profile의 후보 Tool은 실행 전 사용자별 권한으로 필터링하며, 실제 선택되지 않은 후보의 Tool·data claim은 Run 결과에 남기지 않는다.
- 자동 라우터는 `general`, `current_app`, `other_app`, `clarify` 중 하나와 단일 대상 앱만 반환한다.
- 사용자가 명시한 Observer 범위는 현재 화면 범위보다 우선하고, 누락 필드는 현재 Observer 화면 범위로 보완한다.

## 실행 단계
- [x] 지식 의도 판별 서비스와 단위 테스트를 추가한다.
- [x] `email-rag` v2를 등록하고 v1 실행 의미를 보존한다.
- [x] Email chat orchestration에서 판별 결과에 따라 RAG를 조건부 실행한다.
- [x] Runtime의 tool/access metadata를 실제 RAG 사용 여부와 맞춘다.
- [x] Email ChatWidget 문구와 frontend 테스트를 갱신한다.
- [x] backend/frontend/audit 검증을 수행한다.
- [x] Appstore·Line Dashboard·Observer 공통 판별과 Profile v2를 추가한다.
- [x] 동적 도구 미사용 시 앱 Profile 기반 일반 답변으로 전환한다.
- [x] 모든 앱 UI 문구와 고정 앱 prompt 의미를 자동 사용으로 통일한다.
- [x] offsite dummy 판별 계약과 전체 회귀 테스트를 갱신한다.
- [x] 전체 검증과 결정 기록을 완료한다.
- [x] `auto-knowledge` Profile과 권한 필터링된 상위 라우터를 추가한다.
- [x] 현재 화면 범위 병합과 교차 앱 범위 누락 명확화 응답을 구현한다.
- [x] ChatWidget을 두 모드 선택 UI로 교체하고 현재 앱 전용을 기본값으로 둔다.
- [x] offsite dummy 자동 라우팅 계약과 회귀 테스트를 추가한다.
- [x] 두 모드 전체 검증과 결정 기록을 완료한다.

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.assistant` — 76개 통과
- `npm --prefix apps/web run test -- --run src/features/assistant` — 96개 통과
- `npm run agent:audit:ui` — 통과
- `npm run agent:audit:web-boundary` — 통과
- `npm run agent:audit:api-boundary` — 통과
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py makemigrations --check --dry-run` — 변경 없음
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --build --entrypoint python adfs ...` — 현재 앱 우선, 다른 앱 전환, 일반 답변 자동 라우팅 계약 통과

## 위험과 대응
- 위험: 판별 모델이 메일 후속 질문을 일반 질문으로 오분류할 수 있다.
- 대응: 최근 대화 문맥을 함께 전달하고, 불명확하거나 파싱할 수 없는 결과는 RAG 사용으로 처리한다.
- 위험: 자동 판별 호출로 Email 답변 latency가 증가한다.
- 대응: temperature 0의 짧은 구조화 출력과 작은 출력 한도를 사용하고, RAG가 필요 없을 때 검색 호출을 절약한다.
- 위험: RAG를 사용하지 않은 답변이 불필요한 데이터 claim에 묶일 수 있다.
- 대응: 실제 검색 여부에 따라 tool key와 RAG data claim을 조건부로 구성한다.
- 위험: 자동 판별 실패로 앱 데이터 질문에서 필요한 도구를 실행하지 않을 수 있다.
- 대응: 판별 실패·미지원 응답은 기존처럼 도구를 실행하는 보수적 fallback을 적용한다.
- 위험: offsite dummy가 구조화 판별 응답을 지원하지 않아 항상 fallback할 수 있다.
- 대응: dummy OpenAI 호환 endpoint에 앱별 결정적 판별 계약을 함께 구현한다.
- 위험: 자동 후보가 선택되기 전에 불필요한 권한 또는 data claim이 저장될 수 있다.
- 대응: 후보는 실행 전 Tool별 권한으로 필터링하고, Run 완료 시 실제 선택 Tool과 결과 요구사항으로 덮어쓴다.
- 위험: 다른 앱의 Observer 요청이 불완전한 범위로 잘못된 장비를 분석할 수 있다.
- 대응: 명시 범위를 우선 병합한 뒤 장비·기간·로그 유형이 모두 확정된 경우에만 분석하고, 아니면 명확화 질문을 반환한다.

## 진행 기록
- 2026-08-15: Email부터 적용하고 ON은 자동 사용, OFF는 일반 대화로 유지하는 범위를 확정했다.
- 2026-08-15: 실행 의미 재현을 위해 기존 v1은 유지하고 자동 판별을 v2로 추가하기로 했다.
- 2026-08-15: 운영 판별 실패는 RAG fallback, dummy mode는 결정적 로컬 판별로 구현했다.
- 2026-08-15: backend/frontend 테스트와 UI/backend boundary audit, migration check를 완료했다.
- 2026-08-15: 기본 `api` 기동은 기존 PostgreSQL MultiXact wraparound 오류로 실패해 일회성 컨테이너의 테스트 DB로 검증했다.
- 2026-08-15: 사용자 결정에 따라 자동 사용 범위를 모든 ChatWidget 앱으로 확장했다.
- 2026-08-15: Appstore·Line Dashboard·Observer Profile v2와 수동 앱 prompt 제한, 전체 UI 문구, offsite dummy 계약을 적용하고 전체 검증을 완료했다.
- 2026-08-15: 사용자 결정에 따라 ON/OFF 대신 `현재 앱 지식만 사용`과 `자동 지식 선택` 두 모드로 확장하며, 현재 앱 전용을 기본값으로 확정했다.
- 2026-08-15: Observer는 사용자 명시 범위를 우선하고, 다른 앱에서 필수 범위가 없으면 명확화 질문을 반환하기로 확정했다.
- 2026-08-15: `auto-knowledge` Profile, 권한 후보 필터, 두 모드 UI, offsite dummy와 76개 backend·96개 frontend 회귀 검증을 완료했다.
