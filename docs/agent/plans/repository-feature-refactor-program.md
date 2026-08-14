# ExecPlan: 저장소 Feature 아키텍처 유지보수성 강화 프로그램

## 목표
- frontend/backend feature 경계를 deterministic audit와 CI로 강제한다.
- backend allowlist를 0건으로 만들고 facade에는 명시적 re-export만 남긴다.
- `apps/web/src/lib`의 domain API/query/UI를 소유 feature로 이동한다.
- 기존 hotspot의 신규 증가를 차단하고 우선순위 feature를 책임별 모듈로 분해한다.
- 사용자 노출 동작과 운영 데이터를 유지하면서 참조 없는 내부 호환 코드만 제거한다.

## 현재 상태
- 2026-08-14 기준 frontend/backend boundary, hotspot, UI, docs audit는 모두 통과한다.
- backend allowlist와 `apps/web/src/lib/account`은 제거됐다.
- L0/TTTM/L3 Spider와 PM Comparison의 service facade에는 명시적 re-export만 남아 있다.
- 기존 production/test hotspot은 파일·test class 기준선보다 증가할 수 없고 신규 파일에는 고정 임계값이 적용된다.
- GitHub Actions는 frontend test/lint/build/audit와 격리된 backend 전체 test/check/migration drift를 실행한다.
- test Compose 기준 backend 1,082개와 frontend 178개 테스트가 통과한다.
- L3 Spider와 PM Comparison backend service 구현은 책임별 module로 분리됐고, PM Spider·Access Stats·L3 Spider summary/guide/trellis frontend hotspot은 모두 1,000줄 아래로 분리됐다.
- 나머지 backend view/selector/test hotspot은 기준선 증가가 차단된 후속 수직 배치 대상이다.

## 범위
- 수정: `apps/api`, `apps/web`, `scripts/agent`, `.github/workflows`, test 전용 Compose, 관련 문서와 이 ExecPlan.
- 유지: 공개 route, 권한, API 응답, React Query key, 사용자 UI 상태, 운영 데이터와 실제 사용이 입증된 auth/env/offsite 계약.
- 제외: 사용자 노출 기능 전체 삭제, applied migration 수정, 별도 요청 없는 commit/push.

## 설계
- Backend domain app은 단일 `views.py`/`selectors.py`/`tests.py`와 같은 이름의 package를 모두 허용한다. package facade는 명시적 re-export만 갖는다.
- Cross-domain import는 `services` 또는 `selectors` facade만 허용하며 production/test에 동일하게 적용한다.
- Frontend cross-feature import는 선언된 `auth -> account`, `emails -> account`, `line-dashboard -> account` 관계와 public facade에만 허용하며 그 밖의 조합은 non-feature orchestration layer에서 수행한다.
- `lib`는 app-shell context, framework adapter, 범용 helper만 소유하며 domain HTTP, React Query hook, 업무 UI를 소유하지 않는다.
- LOC audit는 현재 파일별 기준선을 저장한다. production 1,000줄, test 1,500줄, test class 500줄을 넘은 기존 파일은 줄 수 증가를 실패 처리하고 신규 초과는 즉시 실패 처리한다.
- JSON/API와 DB schema는 이번 책임 분해에서 변경하지 않는다. 추후 schema 정리가 필요하면 새 migration으로 expand -> backfill -> verify -> contract 순서를 따른다.
- CI는 PostgreSQL과 API test container만 기동하는 별도 Compose를 사용하고, 외부 ADFS/RAG/Mail/MinIO 호출은 test env/fake로 차단한다.

## 실행 단계
- [x] 현재 audit, allowlist, hotspot, `lib` 소유권, CI 상태를 조사한다.
- [x] 경계 규칙 문서와 backend/frontend audit를 dependency graph, facade purity, allowlist usage, LOC 기준선까지 강화한다.
- [x] `pm_comparison/writer.py`, Auth/Account test import, Data Movement 상위 test import를 정리하고 allowlist를 제거한다.
- [x] L0/TTTM/L3 Spider와 PM Comparison service facade 실행 로직을 구현 service module로 이동한다.
- [x] `lib/account`을 Account feature로 이동하고 Auth/Emails/Line Dashboard가 Account facade만 사용하도록 정리한다.
- [x] `lib/affiliation`과 `lib/assistant`에는 shell/application bridge만 남긴다.
- [x] 기존 production/test hotspot의 신규 증가를 차단하는 파일·test class 기준선을 추가한다.
- [x] L3 Spider·PM Comparison service와 PM Spider·Access Stats·L3 Spider frontend hotspot을 책임별 module로 분리한다.
- [x] `LineSettingsPage`를 recipient/mapping/notification controller hook으로 분리한다.
- [ ] Account/Auth부터 Spider/Data Movement까지 남은 backend view·selector·test hotspot을 수직 feature 배치로 분리한다.
- [x] 전용 backend CI Compose와 전체 PR guardrail을 추가한다.
- [x] 상대 import와 package형 view/selector까지 경계 audit가 탐지하도록 보강하고 회귀 test를 추가한다.
- [x] PR base부터 HEAD까지 committed whitespace 오류를 CI에서 검사한다.
- [x] 전체 검증을 실행하고 기준선 및 진행 기록을 갱신한다.

## 검증
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py check`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py makemigrations --check --dry-run`
- `npm run web:test -- --run`
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit`
- `git diff --check`

## 위험과 대응
- 위험: 대형 facade 분해 중 module-level patch target이나 public symbol이 달라질 수 있다.
- 대응: 모든 저장소 import와 test patch path를 정적 검색하고 public facade에서 사용 중 symbol을 명시적으로 re-export한다.
- 위험: Account facade 변경이 Auth/Emails/Line Dashboard까지 동시에 깨뜨릴 수 있다.
- 대응: 선언된 세 의존만 facade import로 허용하고 dependency graph·순환 audit와 frontend 전체 test/build를 함께 실행한다.
- 위험: 전체 backend suite가 외부 서비스 또는 오래 걸리는 데이터 test에 의존할 수 있다.
- 대응: test 전용 env에서 외부 호출을 차단하고 feature test부터 실행한 뒤 전체 suite 결과를 기록한다.
- 위험: 대형 test 분해가 테스트 discovery나 patch 경로를 바꿀 수 있다.
- 대응: 기존 test label을 기준으로 전후 discovered test 수와 결과를 비교한다.
- 위험: 정규식 기반 frontend import 수집이 side-effect 또는 multiline 구문을 놓칠 수 있다.
- 대응: import specifier 수집과 실제 feature 경로 해석을 분리하고 양성/음성 fixture로 고정한다.

## 진행 기록
- 2026-08-01: VOC pilot, frontend test 기반, route lazy loading, Account/Auth/Activity 계약 정리를 완료했다.
- 2026-08-03: Activity/VOC 보완과 frontend test CI 단계를 완료했다.
- 2026-08-14: 기존 프로그램을 현재 유지보수성 강화 계획으로 갱신했다. 정적 audit 4종 통과, backend allowlist 4건, 주요 LOC hotspot, `lib/account` 잔존, Django CI 누락을 확인했다.
- 2026-08-14: 개발 Compose에는 PostgreSQL 일부와 worker만 실행 중이고 `api` service는 없어 전체 Django test 기준선을 전용 test Compose 구현 단계로 이관했다.
- 2026-08-14: backend allowlist 4건을 제거했다. 참조 없는 PM writer를 삭제하고 Auth/Data Movement test의 cross-domain 내부 import를 facade/service-selector 경계로 변경했다.
- 2026-08-14: L0/TTTM/L3/PM service facade의 실행 로직을 구현 module로 이동하고 facade purity audit를 추가했다.
- 2026-08-14: `lib/account`을 제거하고 Account API/hook/utils/UI를 feature로 이동했다. `lib/affiliation`의 HTTP/query와 `lib/assistant`의 profile/surface 설정도 소유 feature로 이동했다.
- 2026-08-14: 선언된 frontend dependency graph와 순환, lib domain 소유권, LOC/test class baseline 증가를 감사하도록 guardrail을 강화했다.
- 2026-08-14: internal network 기반 `docker-compose.test.yml`과 PostgreSQL `pg_trgm` 초기화를 추가하고 PR CI에 backend 전체 test/check/migration drift 및 전체 audit를 필수화했다.
- 2026-08-14: L3 Spider service를 metadata/rules/query/state로, PM Comparison service를 payload/trace/OES/contracts/orchestration으로 분리했다. 두 facade와 공개 symbol은 유지했다.
- 2026-08-14: PM Spider ranking/trace/OES, Access Stats controller/panel/utils, L3 Spider summary/guide/trellis를 분리해 해당 기존 frontend hotspot 기준선 5건을 제거했다.
- 2026-08-14: `LineSettingsPage`의 recipient, target mapping, notification action을 controller hook 3개로 분리해 마지막 frontend production hotspot 기준선을 제거했다.
- 2026-08-14: backend 1,082개, frontend 178개 테스트와 Django check/migration drift, frontend lint/build, 전체 agent audit를 통과했다. schema/API 계약 변화가 없어 migration은 생성하지 않았다.
- 2026-08-14: 코드 리뷰에서 package형 backend view/selector와 상대 import, frontend 상대/side-effect import, CI whitespace 비교 범위의 guardrail 누락을 확인해 보강 배치를 시작했다.
- 2026-08-14: backend 상대 import 및 package형 view/selector, frontend 상대/side-effect import를 실제 경로 기준으로 감사하도록 보강했다. 회귀 test 12개를 `agent:audit`에 연결하고 PR/push committed diff의 whitespace 검사를 검증했다.

## 사용자 승인 대기 후보
- VOC의 값이 하나뿐인 `app=기타` UI와 DB 필드 제거 여부.
- 저장소 내부에서만 참조되는 `/react-logo-preview` route 제거 여부.
- 이미지 asset이 존재하지 않아 깨져 있는 `/teamstaff` 화면을 폐기할지, 새 asset으로 복구할지 여부.
