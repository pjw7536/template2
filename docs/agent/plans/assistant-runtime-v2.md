# ExecPlan: Assistant Runtime v2

## 목표
- Profile, Tool, Provider 경계를 분리하고 현재 권한을 모든 실행·열람·재사용 시점에 재검증한다.
- partition별 메모리와 versioned access requirements를 Run·메시지·요약·제목에 보존한다.
- 하나의 `/api/v1/assistant/turns/stream` SSE 계약으로 send/edit/regenerate/retry/replay를 제공한다.
- 표준 Turn 외 실행·저장 호환 경로를 제거해 단일 실행 계약만 유지한다.

## 현재 상태
- `AssistantGeneration`과 `AssistantMessage.generation`이 실행과 메시지 연결의 source of truth다.
- 대화방 current branch, generation lease, OpenWebUI streaming, Email RAG, Observer 분석 구현이 이미 존재한다.
- 작업 트리에 Portal 앱 문맥과 공유 메모리 관련 사용자 변경이 staged 상태로 존재하므로 이를 보존한다.
- Portal, Email, Observer 프론트 실행은 표준 Turn API로 전환했다.
- 기존 채팅·Observer 분석·Generation lease·브라우저 메시지 저장 경로는 더 이상 제품 호출자가 없으며 제거 대상이다.
- Email RAG는 `emails` data scope 하나로 통일했고, Email/Observer 최근 history와 Portal app context provenance를 Provider 경계에 연결했다.
- legacy backfill은 migration sentinel 교체와 terminal unresolved 규칙으로 재실행 안정성을 확보했다.
- Provider는 OpenAI 호환 stream으로 실행하며 disconnect/timeout 취소와 Run persistence fencing을 적용했다.

## 범위
- 수정: `api.assistant` 모델·serializer·selector·service·view·migration·management command·tests.
- 수정: Assistant frontend 공통 Profile/SSE/Turn hook와 기존 호출의 서버-history 전환.
- 수정: Assistant API/module 문서와 관련 agent 결정 기록.
- 수정: OpenAI 호환 LLM payload를 `stream: true`로 전환하고 `apps/adfs_dummy`의 chunk·구조화 응답 계약을 동기화한다.
- 미수정: 외부 RAG/LLM URL, Observer 데이터 selector, auth env 이름과 Compose endpoint 계약.

## 설계
- Profile registry는 지원 버전과 provider/tool/partition/account scope/timeout 정책을 불변 객체로 제공한다.
- `access_requirements.version=1`은 Account scope와 dataClaims를 정규화·합산하며 현재 validator registry로 검증한다.
- message/summary/title serializer는 권한 실패 시 fail-closed placeholder 또는 일반 제목을 반환한다.
- Runtime은 외부 호출과 정규화만 담당하고 Turn service가 권한, Run, branch, 저장, replay, SSE 수명주기를 담당한다.
- migration은 nullable/default 기반 확장만 수행하며 legacy backfill은 재실행 가능한 command로 분리한다.
- 외부 endpoint와 env 이름은 유지한다. LLM payload의 `stream: true` 변경은 offsite mock에 동일하게 반영하고 Compose URL은 바꾸지 않는다.
- `AssistantGeneration`은 Run 저장 모델로 유지하되 공개 lease API와 legacy acquire service는 제거한다.
- conversation message endpoint는 GET/DELETE만 유지하고 user/assistant 저장은 Turn service만 수행한다.
- Observer 데이터 분석 구현은 `api.observer.services` facade로만 호출하고 Observer HTTP 분석 endpoint 및 assistant selector reverse dependency는 제거한다.
- Email RAG group/mailbox의 선택·저장·재검증은 모두 `emails` data scope 하나만 사용한다. sender 개인 그룹과 `rag-public`은 Email Account scope를 통과한 Turn에서만 추가한다.
- `appContextKey`는 Profile과 분리된 prompt provenance로 저장하고 서버 allowlist 또는 정규화된 Observer Tool 입력으로 검증한다. 권한 판정에는 사용하지 않는다.
- partition summary의 `message_count` 이후 메시지만 recent history로 사용하고, 실제 token budget에 포함된 메시지·summary 요구사항만 Run에 합산한다.
- 구조화 출력이 필요한 Email/Observer도 upstream은 `stream:true`로 소비한다. Portal은 검증된 token을 즉시 전달하고, Email/Observer는 전체 구조화 응답 검증 후 안전한 block 단위로 전달한다.
- Provider 실행은 취소 token을 가진 worker와 heartbeat 기반 SSE lifecycle로 감싼다. disconnect/timeout은 response/session을 닫고, 최종 저장은 활성 Run·lease·예상 branch head를 원자적으로 다시 확인한다.
- backfill은 legacy row만 처리하고 명시적 우선순위로 분류한다. `legacy-unresolved`는 terminal 상태이며 재실행으로 완화되지 않고, 성공 분류 시 migration sentinel은 합집합이 아니라 교체한다.
- 신규 Turn은 app context를 필수로 검증하며 bare OpenWebUI context, 일반 텍스트 Email 응답, 코드펜스 Observer 응답을 현재 계약으로 추정하지 않는다.

## 실행 단계
- [x] Profile/access requirement/partition registry와 schema migration을 추가한다.
- [x] 권한 인식 selector/serializer와 legacy server-history 전환을 구현한다.
- [x] 저장 없는 Runtime과 Turn service, 표준 SSE API를 구현한다.
- [x] fail-closed legacy mapper와 resumable backfill command를 추가한다.
- [x] frontend profile key와 표준 SSE parser를 추가하고 `useChatSession`을 Turn client 하나로 전환해 기존 history 전송을 제거한다.
- [x] 보안·멱등·replay·disconnect·partition 회귀 테스트와 문서를 갱신한다.
- [x] Django/web/audit 검증을 실행하고 결과를 기록한다.
- [x] legacy Assistant/Observer 실행 endpoint와 공개 Generation lease API를 제거한다.
- [x] frontend legacy sender/history/브라우저 저장/generation fallback을 제거한다.
- [x] 호환 serializer·service·utility·tests와 현재 문서의 legacy 계약을 제거한다.
- [x] 단일 Turn 계약 기준 Django/web/audit 검증을 다시 실행한다.
- [x] Email RAG data scope를 `emails`로 단일화하고 교차 scope 회귀 테스트를 추가한다.
- [x] app context provenance와 summary 이후 memory composer를 Turn/Runtime에 연결한다.
- [x] 권한 혼합 summary·검색을 fail-closed pagination/cursor 계약으로 수정한다.
- [x] OpenAI 호환 streaming transport, 취소 worker, heartbeat와 Run persistence fencing을 구현한다.
- [x] legacy backfill을 idempotent fail-closed command로 고치고 재실행 테스트를 추가한다.
- [x] Provider 오류·source/block 출력 경계를 서버에서 제한한다.
- [x] `useChatSession`의 서버 상태를 React Query 하나로 수렴하고 Turn transient state를 분리한다.
- [x] 전체 backend/web/offsite/boundary 검증을 다시 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.observer api.rag api.account api.emails`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run web:test`
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit`

## 위험과 대응
- 위험: legacy 데이터에 정확한 provenance가 없다.
- 대응: `legacy-unresolved`로 분류하고 현재 권한에서 fail-closed하며 command 보고서로 분리한다.
- 위험: 과거 Profile의 완화된 정책이 replay에 사용될 수 있다.
- 대응: 저장 버전은 의미 재현에만 쓰고 현재 Profile/Tool authorization floor와 저장 요구사항을 합산한다.
- 위험: SSE disconnect 후 완료 메시지가 저장될 수 있다.
- 대응: generator close를 감지해 upstream iterator를 닫고 Run을 stopped로 원자 종료한다.
- 위험: 구조화 JSON을 token 그대로 UI에 보내면 Email source/Observer evidence 계약이 깨질 수 있다.
- 대응: upstream transport는 실제 stream으로 취소 가능하게 만들되 구조화 Provider는 검증 완료 후 표시 가능한 block만 delta로 방출한다.
- 위험: 권한에 따라 summary 대상 집합을 압축하면 `message_count`가 같은 branch에서 다른 의미가 된다.
- 대응: batch 중 하나라도 잠기면 cursor를 전진시키지 않고, 권한 복구 후 동일한 연속 구간을 다시 처리한다.

## 진행 기록
- 2026-08-13: 제공된 최종 계획과 저장소 상태를 대조하고 구현 범위 및 외부 contract 비변경 원칙을 확정했다.
- 2026-08-13: versioned Profile, access requirements, partition memory, Runtime/Turn API, fail-closed serializer, backfill command를 구현했다.
- 2026-08-13: Portal, Email, Observer 프론트를 표준 Turn SSE로 전환하고 Observer page context의 레거시 sender/history 합성을 제거했다.
- 2026-08-13: 기존 generation 및 Observer analysis endpoint는 schema 배포와 backfill 완료 전 제거할 수 없으므로 호환 계층으로 유지했다. 외부 provider URL·payload에는 변경이 없다.
- 2026-08-13: Assistant·Observer·RAG·Account·Emails 426개 테스트, migration drift 검사, web 185개 테스트, lint, production build, frontend/backend/UI/docs audit가 통과했다. 기존 `apps/web/dist`의 root 소유 파일은 건드리지 않고 임시 출력 경로에서 build를 검증했다.
- 2026-08-13: 사용자 요청에 따라 배포 호환 계층을 유지한다는 이전 결정을 철회하고 표준 Turn 외 실행·저장 경로 제거를 시작했다. RAG/OpenWebUI 외부 provider contract와 backfill은 유지한다.
- 2026-08-13: Assistant/Observer legacy 실행 endpoint, Generation lease·브라우저 메시지 저장 API, frontend sender·route-state handoff, 구형 env alias를 제거했다. 단일 Turn 기준 backend 395개·web 157개 테스트, migration drift, lint, 임시 경로 production build와 전체 audit가 통과했다.
- 2026-08-13: 구조 리뷰에서 Email scope 혼선, memory 유실/중복, app provenance 유실, 비취소 동기 Provider, stale Run 저장, 권한 검색·summary cursor와 backfill 멱등성 결함을 확인해 배포 전 remediation 단계를 추가했다.
- 2026-08-13: Email scope 단일화, memory cursor, app provenance, 실제 stream/cancellation, 저장 fencing, fail-closed 검색·summary, backfill 재실행, React Query 단일 원본 구조를 구현했다.
- 2026-08-13: 신규 실행 경로의 bare context와 Email/Observer 구조화 출력 fallback을 제거하고 로컬 `adfs_dummy`를 단일 JSON 및 OpenAI SSE 계약에 맞췄다.
- 2026-08-13: Runtime memory provenance를 연결된 Run의 partition으로만 제한하고, sync Turn Provider와 일반 텍스트·코드펜스 구조화 응답 호환 경로를 제거했다.
- 2026-08-13: Provider 완료 뒤 pre-commit heartbeat에서 연결이 끊긴 경우 Run을 `stopped`로 종료하고 Assistant 답변을 저장하지 않는 회귀 테스트를 추가했다.
- 2026-08-13: 최신 코드 기준 backend 410개·web 159개 테스트, migration drift 검사, lint, production build, frontend/backend/UI/docs audit가 통과했다. backfill dry-run은 처리·미분류 0건이었고, 재기동한 `adfs_dummy`에서 Email strict JSON을 OpenAI SSE chunk로 반환하는 contract smoke test가 통과했다.
