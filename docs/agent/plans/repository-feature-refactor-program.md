# ExecPlan: 저장소 전체 Feature 리팩토링 프로그램

## 목표
- frontend/backend/pipeline을 수직 feature 단위로 순회하며 독립성과 유지보수성을 높인다.
- 저장소 내부 호출자가 없는 호환 코드와 중복 정규화, 무의미한 fallback을 제거한다.
- 기존 데이터는 명시적으로 이관하고 사용자 노출 동작은 승인 없이 제거하지 않는다.

## 현재 상태
- frontend/backend boundary audit와 frontend lint/build는 통과한다.
- frontend 자동화 테스트가 없고 초기 JavaScript chunk가 모든 feature를 포함한다.
- `docs/agent/plans/feature-independence-cleanup.md`의 기존 경계 정리는 완료된 상태다.
- 첫 수직 pilot은 `voc`이며 API 컨테이너 기준 테스트를 실행해야 한다.

## 범위
- 수정할 영역: `apps/web`, `apps/api`, 소유 feature와 연결된 `airflow`, 문서와 agent audit.
- 수정하지 않을 영역: 승인되지 않은 사용자 기능 제거, 보안 개선, 적용된 migration 수정.

## 설계
- HTTP JSON은 feature별 문서화된 camelCase 계약 하나만 사용하고 Python/DB는 snake_case를 유지한다.
- legacy DB 값은 새 data migration으로 정규화한 뒤 호환 분기를 제거한다.
- localStorage/sessionStorage는 한 배포에서 이관하고 다음 배포에서 변환기를 제거한다.
- frontend는 Vitest/React Testing Library characterization test를 먼저 추가한다.
- backend는 serializer가 schema/validation, selector가 read, service가 write, view가 HTTP를 담당한다.
- 외부 프로토콜과 정상적인 empty/error UX fallback은 이유와 테스트가 있으면 유지한다.

## 실행 단계
- [x] 공통 frontend 테스트 기반과 route-level lazy loading을 추가한다.
- [x] VOC pilot의 API 계약과 책임 분리를 정리한다.
- [x] VOC frontend/backend 회귀 테스트와 문서를 갱신한다.
- [x] common/health와 frontend shell feature를 순회한다.
- [x] account/auth, activity/access-stats를 순회한다.
- [x] 리뷰에서 확인된 Activity 빈 출처, VOC strict validation, frontend lock/CI 누락을 보완한다.
- [ ] appstore와 data_movement table app을 순회한다.
- [ ] Spider 계열 feature를 순회한다.
- [ ] emails, rag/assistant를 순회한다.
- [ ] drone/line-dashboard와 observer를 순회한다.

## 검증
- `npm run web:test -- --run`
- `npm run web:lint`
- `npm run web:build`
- `npm run agent:audit`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.<feature>`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `git diff --check`

## 위험과 대응
- 위험: legacy 분기가 실제 운영 데이터 또는 내부 job에서 사용될 수 있다.
- 대응: import, route, API, command, DAG, 문서 호출자를 모두 확인하고 데이터는 먼저 이관한다.
- 위험: 큰 feature를 한 번에 정리하면 회귀 원인 추적이 어렵다.
- 대응: feature별 characterization test와 검증을 통과한 뒤 다음 단위로 이동한다.
- 위험: 사용자 bookmark나 수동 업무 흐름은 정적 검색만으로 확인할 수 없다.
- 대응: 사용자 노출 route와 기능은 후보를 보고하고 승인 전까지 유지한다.

## 진행 기록
- 2026-08-01: 전체 프로그램 범위, 삭제 기준, 수직 feature 순서와 VOC pilot을 확정했다.
- 2026-08-01: Vitest/React Testing Library 기반과 VOC frontend contract 테스트를 추가했다.
- 2026-08-01: VOC API를 canonical camelCase 계약으로 축소하고 serializer/selector/service/view 책임을 정리했다.
- 2026-08-01: 주요 route component를 lazy chunk로 분리해 초기 JS chunk를 약 7.38MB에서 0.80MB로 줄였다.
- 2026-08-01: shared account hook의 auth 의존을 feature adapter로 옮겨 lazy chunk 순환 의존을 제거했다.
- 2026-08-01: VOC 9개, common/health 11개 Django 테스트를 fresh test DB에서 통과했다.
- 2026-08-01: frontend 7개 테스트, lint/build, frontend/backend boundary, Django check와 migration drift, 문서 inventory를 통과했다.
- 2026-08-01: 전체 UI audit은 기존 L3 raw color와 측정용 inline style 후보 때문에 실패 신호를 유지했다.
- 2026-08-01: Account SPA 소속 변경·승인·목록·멤버 query를 camelCase 계약으로 단일화하고 snake_case·id·q·page_size 호환 분기를 제거했다.
- 2026-08-01: Account 사용자 pool query에서 snake_case 별칭과 잘못된 limit의 묵시적 기본값 보정을 제거하고 정적 스키마로 이동했다.
- 2026-08-01: Auth 소속 조회를 공용 Account API adapter로 통합했다.
- 2026-08-01: Activity/Access Stats의 limit 묵시적 보정과 app_id·app_name·granularity·pasted_text·source_name 별칭을 제거하고 DRF serializer 계약으로 이동했다.
- 2026-08-01: Account 135개, Auth 31개, Activity 22개 backend 테스트와 frontend 14개 테스트, lint/build, 전후단 경계, Django check·migration drift, 문서 inventory를 통과했다.
- 2026-08-03: Activity의 빈 `sourceName`을 `manual`로 정규화하고 VOC 입력 serializer에서 미정의 필드를 거절하도록 보완했다.
- 2026-08-03: web lockfile에 테스트 의존성을 동기화하고 feature guardrail CI에 frontend 테스트 단계를 추가했다.
- 2026-08-03: frontend 테스트 14개, lint/build, 전후단 경계, 문서 audit, VOC serializer 테스트와 Activity serializer 직접 검증, Django check를 통과했다.

## 사용자 승인 대기 후보
- VOC의 값이 하나뿐인 `app=기타` UI와 DB 필드 제거 여부.
- 저장소 내부에서만 참조되는 `/react-logo-preview` route 제거 여부.
- 이미지 asset이 존재하지 않아 깨져 있는 `/teamstaff` 화면을 폐기할지, 새 asset으로 복구할지 여부.
