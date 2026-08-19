# ExecPlan: Activity·Access Stats 통합

## 목표
- route access 기록, 내부/외부 통계, 수동 입력, tracking catalog와 권한 검사를 하나의 명시적 흐름으로 정리한다.
- 6시간 외부 sync throttle과 admin 수동 입력 규칙을 보존한다.

## 현재 상태
- backend `activity_logs.py` 1,068줄에 기록, 집계, 외부 sync, 수동 CSV parsing이 함께 있다.
- frontend `AccessStatsPanels.jsx`는 842줄이며 tracking catalog는 `src/lib/activity/appAccessCatalog.js`에 있다.
- 개발 DB ActivityLog는 0건으로 운영 사용량 판단 근거가 아니다.

## 범위
- 수정: `api.activity`, `features/access-stats`, app-shell tracker/catalog, external usage env/docs.
- 유지: `/access-stats`, `/api/v1/activity/**`, KST 기간 계산, 6시간 throttle, access-stats user/admin 권한.
- 제외: catalog의 Spider·Teamstaff entry 변경.

## 설계
- service를 recording, aggregation, manual_import, external_sync로 분리하고 selector는 read-only aggregation만 담당한다.
- app route catalog는 app-shell의 단일 frozen catalog로 유지하며 tracker, branding, Access Stats가 같은 appId/name을 읽는다. 제외 scope entry는 그대로 보존한다.
- browser query/body는 `from`, `to`, `period`, `sourceName`, `appName`, `accessCount`, `uniqueUserCount` camelCase만 허용한다.
- 수동 paste의 사용자 입력 header alias는 CSV ingestion contract이므로 한글/legacy header를 유지하되 API JSON alias로 취급하지 않는다.
- frontend server rows/sync state는 React Query만 소유하고 period/filter/dialog text만 local state로 둔다.
- schema/constraint는 유지하고 migration은 없다.

## 실행 단계
- [x] 기록·집계·manual·sync 결과와 권한 characterization을 추가한다.
- [x] backend service/test와 frontend panels/controller를 책임별로 분리한다.
- [x] tracking catalog 단일 소비 경로를 적용한다.
- [x] external sync 성공/실패/throttle과 수동 preview/commit 회귀를 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity`
- `npm run web:test -- --run`, `npm run web:lint`, `npm run web:build`.
- `npm run agent:audit:ui`, `npm run agent:audit:web-boundary`, `npm run agent:audit:api-boundary`.

## 위험과 대응
- 위험: catalog 정리 중 제외 feature의 access tracking이 바뀐다.
- 대응: Spider·Teamstaff entry snapshot을 고정하고 changed-path/fixture로 검증한다.
- 위험: 외부 sync 실패가 throttle timestamp에 반영되지 않는다.
- 대응: 성공·실패 실제 시도 모두 `updated_at`을 갱신하는 transaction test를 유지한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). Auth 뒤에 실행하고 Home shell의 최종 catalog 통합에 입력을 제공한다.
- 복구: DB schema를 바꾸지 않으므로 service/catalog 전환을 되돌린다. 이미 적재된 통계 row와 throttle state는 보존한다.

## 진행 기록
- 2026-08-18: CSV header alias는 유지하고 JSON camelCase만 canonical로 확정했다.
- 2026-08-18: 1,068줄 `activity_logs.py`를 recording 92줄, aggregation 383줄, manual_import 283줄, external_sync 359줄과 51줄 순수 helper로 분리하고 obsolete hotspot 예외를 제거했다. 전체 구현 LOC는 책임 경계와 문서화로 100줄가량 늘었지만 각 파일은 기본 1,000줄 기준 이하다.
- 2026-08-18: 842줄 `AccessStatsPanels.jsx`를 chart 480줄, summary 152줄, manual paste 234줄로 분리했다. React Query hook은 서버 상태를 계속 단독 소유한다.
- 2026-08-18: Activity API 오류를 공통 `code/message/details/fieldErrors`로 전환하고, 외부 sync를 공용 HTTP adapter에 연결했다. 네트워크 timeout/transport 오류의 상태 기록 fallback과 CSV 한글/legacy header ingestion alias는 의도적으로 유지했다.
- 2026-08-18: frozen app access catalog를 tracker·branding·Access Stats가 함께 소비하게 했고 Spider·Teamstaff entry snapshot을 추가했다. Activity 27개, Common 포함 51개, 전체 backend 1,119개와 frontend 191개 테스트, lint/build, migration·권한 무결성, 전체 agent audit를 통과했다.
