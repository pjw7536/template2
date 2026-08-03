# ExecPlan: 핵심 Feature 호환성 유지 리팩토링

## 목표
- `account`, `line-dashboard/drone`, `l3-spider`, `emails`, `observer`의 공개 계약과 UI를 유지하면서 내부 책임을 정리한다.
- feature별 characterization test와 회귀 검증을 추가해 이후 변경의 안전한 기준선을 만든다.

## 현재 상태
- Phase 1에서 frontend/backend 전체 테스트, lint, build, migration, agent audit 기준선을 통과했다.
- 다섯 feature에 순수 변환 회귀 테스트와 최소 책임 분리를 추가했지만 대형 page/view/selector/service는 아직 남아 있다.
- Phase 2는 대형 orchestration과 backend hotspot을 controller/serializer/service 경계로 추가 분리한다.

## 범위
- 수정: 다섯 hotspot의 frontend, backend, 관련 테스트와 계약 문서.
- 제외: 공개 route/API/DB/auth/env 계약 변경, UI 재설계, 다른 feature의 내부 리팩토링.

## 설계
- 각 feature를 backend, frontend, 테스트, 문서까지 하나의 수직 단계로 완료한다.
- backend view는 HTTP 처리, selector는 읽기, service는 write·business orchestration을 담당한다.
- frontend server state는 React Query에 유지하고 component/store에는 UI 상호작용 상태만 둔다.
- facade와 기존 route/API wire shape는 그대로 유지한다.
- model 변경과 migration은 만들지 않는다.

## 실행 단계
- Phase 1 — 기준선 안정화
- [x] 기준선 권한 fixture를 현재 service 계약에 맞추고 hotspot backend 테스트를 통과시킨다.
- [x] Account의 멤버·소속 요청 표시 책임을 페이지에서 분리하고 회귀 테스트를 추가한다.
- [x] Line Dashboard/Drone의 설정·수신인·관리자 target 응답 책임을 분리하고 회귀 테스트를 추가한다.
- [x] L3 Spider의 TTL cache와 chart 선택·표시 책임을 분리하고 회귀 테스트를 추가한다.
- [x] Emails의 mailbox·query·split pane 계산 책임을 inbox controller에서 분리하고 회귀 테스트를 추가한다.
- [x] Observer의 날짜·route·log page 공통 책임을 분리하고 회귀 테스트를 추가한다.
- [x] API/module/inventory 문서를 실제 route와 계약에 맞춘다.
- Phase 2 — 대형 hotspot 분해
- [x] Line Dashboard 조기 알림 CRUD 상태·핸들러와 매핑 계산을 hook/utils로 분리한다.
- [x] Drone SOP target 관리자 입력 검증을 serializer로 이동한다.
- [x] Line Dashboard/Drone 회귀 테스트와 frontend/backend boundary audit을 통과시킨다.
- [x] Account 멤버 페이지의 권한 dialog 표현 책임을 분리하고 DOM 회귀 테스트를 추가한다.
- [x] Account selector의 복잡한 effective access query를 변경 없이 검증할 characterization test 범위를 확정한다.
- [x] L3 Spider의 DataFrame 정규화·샘플링·columnar 직렬화를 analytics service로 분리한다.
- [x] Account effective-access query의 Portal 선행 조건 characterization을 보강한다.
- [x] Observer log pagination 조립 계산을 hook에서 utils로 분리한다.
- [x] Emails split-pane pointer lifecycle을 inbox controller에서 전용 hook으로 분리한다.
- [x] Observer, Emails feature 및 누적 전체 회귀 검증을 통과시킨다.
- Phase 2 — backend hotspot 직렬화/검증 분리
- [x] Observer compact log row/cursor/time 직렬화를 serializers.py로 이동한다.
- [x] Emails view 요청 검증 중복을 serializer 입력 스키마로 이동한다.
- [x] Observer/Emails 및 누적 전체 backend 회귀 검증을 통과시킨다.
- Phase 3 — Observer compact source orchestration 통합
- [x] Observer compact source별 fetch/serialize/cursor metadata를 명시적 registry로 통합한다.
- [x] 일곱 source wiring과 cursor 계약 characterization test를 추가한다.
- [x] Observer 및 누적 backend 경계·migration 회귀 검증을 통과시킨다.
- Phase 4 — Observer detail source dispatch 통합
- [x] Observer 상세 source별 fetch와 payload builder를 명시적 registry로 통합한다.
- [x] 일곱 source 상세 조회 routing과 고유 payload 계약 characterization test를 추가한다.
- [x] Observer 및 누적 backend 경계·migration 회귀 검증을 통과시킨다.
- Phase 5 — Observer source catalog 통합
- [x] 전체 목록·page·detail source metadata를 단일 catalog로 통합한다.
- [x] 기존 log key/fetcher 호환 상수를 catalog 파생값으로 유지하고 완전성 테스트를 추가한다.
- [x] Observer 및 누적 backend 경계·migration 회귀 검증을 통과시킨다.
- Phase 6 — Drone early inform 입력 검증 분리
- [x] Drone early inform 생성·수정 필드 정규화를 입력 serializer로 이동한다.
- [x] serializer와 HTTP validation 오류 계약 characterization test를 추가한다.
- [x] Drone 및 누적 backend 경계·migration 회귀 검증을 통과시킨다.
- Phase 7 — Drone target mapping 중복 검증 통합
- [x] POST·PATCH·DELETE에 세 번 반복된 mapping 공통 필드 검증을 serializer로 통합한다.
- [x] operation별 boolean 기본값/필수 여부와 HTTP 오류 계약 테스트를 추가한다.
- [x] Drone 및 누적 backend 경계·migration 회귀 검증을 통과시킨다.
- Phase 8 — 과도한 구조 변경 최소 원복
- [x] Observer 응답 조립을 serializer로 옮긴 책임 이동을 원복한다.
- [x] Observer private source catalog 구조를 고정하는 테스트를 제거한다.
- [x] L3 Spider raw color를 감사 예외 CSS로 우회한 변경을 원복한다.
- [x] 대상 테스트와 frontend/backend/UI 경계 감사를 통과시킨다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.drone api.emails api.l3_spider api.observer`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run web:test`
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit`

## 위험과 대응
- 위험: 대형 feature를 한 번에 이동하면 공개 응답이나 권한 동작이 달라질 수 있다.
- 대응: characterization test를 먼저 추가하고 작은 책임 단위로 이동한 뒤 feature별 전체 테스트를 실행한다.
- 위험: chart와 virtualization의 동적 style을 기계적으로 제거하면 외관이나 측정 layout이 깨질 수 있다.
- 대응: 시각 결과를 유지하고 불가피한 항목만 구체적인 audit 예외로 기록한다.

## 진행 기록
- 2026-08-03: 대상, 호환 정책, feature별 수직 진행 순서와 검증 gate를 확정했다.
- 2026-08-03: 권한 fixture 기준선 6건을 정상화하고 hotspot backend 678개 테스트 통과를 확인했다.
- 2026-08-03: 다섯 feature의 순수 변환·상태 조립 책임을 분리하고 frontend 회귀 테스트를 추가했다.
- 2026-08-03: L3 TTL cache를 service 모듈로 분리하고 UI audit의 측정 기반 예외를 문서화했다.
- 2026-08-03: 전체 backend 검증에서 발견한 동일 account 권한 계약의 AppStore stale fixture를 함께 정상화했다.
- 2026-08-03: frontend 43개, backend 967개 테스트와 lint, build, 전체 agent audit, migration 무변경 검증을 통과했다.
- 2026-08-03: Phase 2를 시작해 Line Settings의 조기 알림 controller와 매핑 utils를 분리하고 Drone target 관리자 입력 serializer를 추가했다.
- 2026-08-03: Line Dashboard frontend 14개와 Drone backend 281개 테스트, lint/build/경계 audit을 통과했다.
- 2026-08-03: Account Members 권한 dialog를 별도 컴포넌트로 분리해 페이지를 664줄에서 431줄로 축소하고 frontend 전체 51개 테스트를 통과했다.
- 2026-08-03: L3 Spider DataFrame 계산 책임을 analytics service로 이동하고 L3 backend 59개 테스트를 통과했다.
- 2026-08-03: 누적 변경 기준 frontend 51개와 backend 970개 전체 테스트, lint, build, UI/frontend/backend boundary audit, migration 무변경 검증을 통과했다.
- 2026-08-03: Account Portal 비활성 선행 조건을 characterization하고 Observer log pagination 계산과 Emails split-pane lifecycle을 분리했다.
- 2026-08-03: Account 227개와 frontend 전체 55개 테스트, lint/build 및 UI/frontend/backend boundary audit을 통과했다.
- 2026-08-03: 최종 누적 backend 전체 971개 테스트와 migration 무변경 검증을 통과했다.
- 2026-08-03: Observer compact log 직렬화를 serializer로 이동해 selector를 2,136줄에서 1,925줄로 축소하고 Observer 56개 테스트를 통과했다.
- 2026-08-03: Emails 일괄 삭제·이동 입력 검증을 serializer로 통합하고 serializer/HTTP 오류 계약 테스트를 추가해 Emails 65개 테스트를 통과했다.
- 2026-08-03: 누적 backend 전체 975개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: Phase 3에서 backend 허용 구조를 지키기 위해 새 selector 폴더 대신 Observer compact source registry와 공통 page helper를 적용하기로 결정했다.
- 2026-08-03: 일곱 Observer compact source의 fetch/serialize/cursor metadata를 registry로 통합해 selector를 1,925줄에서 1,831줄로 축소했다.
- 2026-08-03: Observer 57개와 누적 backend 전체 976개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: Phase 4에서 상세 source별 fetch/payload builder를 기존 selector 파일 안의 registry로 통합하기로 결정했다.
- 2026-08-03: Observer 상세 fetch/payload builder를 일곱 source registry로 통합해 `get_log_detail` dispatch를 169줄에서 18줄로 축소했다.
- 2026-08-03: Observer 58개와 누적 backend 전체 977개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: Phase 5에서 전체 목록·page·detail source metadata를 단일 catalog로 통합하고 기존 상수는 파생값으로 유지하기로 결정했다.
- 2026-08-03: Observer의 전체 목록·page·detail 세 source registry를 단일 catalog로 통합하고 selector를 1,878줄에서 1,848줄로 축소했다.
- 2026-08-03: Observer 59개와 누적 backend 전체 978개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: Phase 6에서 Drone early inform PATCH의 ID·activity 순서는 유지하고 생성·수정 필드 정규화만 serializer로 이동하기로 결정했다.
- 2026-08-03: Drone early inform 생성·수정 필드 정규화를 serializer로 이동해 view class를 335줄에서 317줄로 축소하고 validation 계약 테스트를 추가했다.
- 2026-08-03: Drone 285개와 누적 backend 전체 982개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: Phase 7 사전 진단에서 target mapping POST·PATCH·DELETE의 동일 4필드 검증이 세 번 반복됨을 확인하고 이 schema 중복만 이동하기로 결정했다.
- 2026-08-03: Target mapping 공통 4필드와 operation별 boolean 검증만 serializer로 통합하고 auth·service·응답 흐름은 변경하지 않았다.
- 2026-08-03: Drone 289개와 누적 backend 전체 986개 테스트, backend boundary audit, migration 무변경 및 diff 무결성 검증을 통과했다.
- 2026-08-03: 수동 검토에서 Observer serializer 책임 이동, private catalog 구조 테스트, L3 raw color의 예외 CSS 이동을 과도한 변경으로 판정하고 해당 범위만 원복하기로 했다.
- 2026-08-03: Observer serializer를 schema/validation 전용으로 복구하고 response builder는 기존 selector 흐름으로 되돌렸으며 private catalog 구조 테스트를 제거했다.
- 2026-08-03: L3 legend 상태색을 원래 컴포넌트로 복구하고 기존 시각 계약임을 파일 단위 UI audit 예외로 명시했다.
- 2026-08-03: Observer 58개, backend 전체 985개, frontend 55개 테스트와 lint/build, migration 무변경, frontend/backend/UI audit 통과를 확인했다.
