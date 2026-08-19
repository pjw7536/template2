# ExecPlan: Account 사용자·소속·접근 권한 단순화

## 목표
- Account를 사용자, 소속, scope 접근과 data scope의 단일 source of truth로 유지하면서 대형 view/selector/test와 중복 입력 계약을 분리한다.
- 기존 승인·감사·동시성 불변조건과 사용자 데이터를 보존한다.

## 현재 상태
- `views.py` 1,248줄, `selectors.py` 2,533줄, `services/access_control.py` 1,652줄, `tests.py` 8,954줄과 `admin.py` 1,101줄이 hotspot이다.
- Portal 선행 조건, `user/admin`, 소속 capability, audit log, pending unique와 lock ordering은 `docs/agent/decisions.md`에 확정돼 있다.
- Auth, Activity, AppStore, VOC, Emails, Drone, Assistant가 Account facade를 소비한다.

## 범위
- 수정: Account backend, Account frontend, 허용된 Auth/Emails/Line Dashboard facade 소비부, 관련 문서/tests.
- 유지: `/settings/**`, `/api/v1/account/**`, DB table과 audit history, canonical scope key.
- 제외: Spider·Teamstaff scope row와 관련 catalog/migration.

## 설계
- view를 affiliation/access-policy/access-matrix/user-pool/audit/sync package module로 나누고 HTTP parsing만 둔다.
- selector를 affiliation/access/effective-access/user-pool/audit module로 나누며 facade가 현재 공개 symbol을 명시적으로 재수출한다.
- `access_control.py`의 resolve, decision write, policy bulk apply, integrity 검사를 각각 service module로 분리한다.
- request/query는 camelCase만 허용하고 현재 Account의 canonical `scopeKey`, `userId`, `dataScopeMode`, `affiliationIds`, `pageSize`, `cursor`를 유지한다.
- error는 공통 shape를 사용하며 Portal 미승인은 `scope_access_required`와 `scope="portal"`을 유지한다.
- frontend는 React Query cache를 server state로 유지하고 dialog/filter/selection만 component state에 둔다. accountApi query key 중복을 제거하되 invalidate 범위는 현재 endpoint 단위로 유지한다.
- schema 삭제는 없다. 기존 migration은 불변이며 새 migration도 만들지 않는다.
- `check_access_permission_integrity --phase pre-migration/post-migration`을 모든 Account 변경의 DB gate로 사용한다.

## 실행 단계
- [x] endpoint별 request/response/error/permission characterization test를 추가한다.
- [x] view/selector/service/test를 책임별 package로 이동한다.
- [x] camelCase 외 입력을 400으로 고정하고 저장소 소비자를 갱신한다.
- [x] Account frontend query/controller와 대형 page 책임을 분리한다.
- [x] downstream Auth·Activity·AppStore·VOC·Emails·Drone·Assistant facade test를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase pre-migration`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth api.activity api.appstore api.voc api.emails api.drone api.assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration`
- `npm run web:test -- --run`, `npm run agent:audit:web-boundary`, `npm run agent:audit:api-boundary`.

## 위험과 대응
- 위험: effective access query 분리가 권한 결과나 query 수를 바꾼다.
- 대응: 동일 fixture의 scope matrix와 query-count characterization을 전후 비교한다.
- 위험: lock 순서 변경으로 동시 승인 경쟁이 깨진다.
- 대응: `Affiliation.id` 오름차순 lock과 마지막 manager 검사를 service test로 고정한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). Platform Common 뒤에 실행하고 Auth·Activity·AppStore·VOC·Emails·Drone·Assistant의 선행 계획이다.
- 복구: schema 변화가 없으므로 facade 공개 symbol을 유지한 채 module 이동과 canonical input 전환을 역순으로 되돌린다. pre/post integrity가 다르면 rollback 전에 쓰기를 중지한다.

## 진행 기록
- 2026-08-18: 기존 권한 결정과 cross-feature 소비자를 변경 불변조건으로 확정했다.
- 2026-08-18: 실제 management command가 `pre-migration/post-migration` phase만 허용함을 확인해 DB gate 명령을 교정하고 재동결했다.
- 2026-08-18: Account HTTP body/query와 Airflow sync를 camelCase 하나로 고정하고 성공 응답의 소속 옵션과 오류 응답을 canonical 계약으로 전환했다. snake_case 거절 및 성공 응답 characterization을 별도 test module에 추가했다.
- 2026-08-18: `views.py`를 `views/` facade·external sync·user pool로, `selectors.py`를 명시적 `selectors/` facade·query·affiliation option으로 분리했다. 감사 저장/직렬화는 `access_audit.py`로 이동했고 기존 공개 facade와 patch 지점은 보존했다.
- 2026-08-18: 주요 hotspot은 view 1,248→1,066줄, selector query 2,533→2,481줄, access control 1,652→1,456줄, 기존 tests 8,954→8,948줄로 감소했다. 신규 characterization test와 명시적 facade LOC는 별도 파일에 두었고 기준선 숫자는 올리지 않았다.
- 2026-08-18: Account 230개 test, downstream Auth·Activity·AppStore·VOC·Emails·Drone·Assistant 524개 test, Airflow contract test, frontend Account 5개 test·lint·임시 outDir production build, pre/post integrity, check, migration drift와 backend/frontend boundary·hotspot 감사를 통과했다.
