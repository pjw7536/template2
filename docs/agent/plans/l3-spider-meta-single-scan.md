# ExecPlan: L3 Spider Meta 단일 집계 조회

## 목표
- cold 상태의 `/meta` 요청에서 `daily_run_stats` 전체 조합 조회를 정확히 한 번만 실행한다.
- 복합 PK와 중복되는 `DISTINCT`를 제거해 PostgreSQL 정렬/해시 비용을 줄인다.
- 첫 페이지 진입에서는 완료 날짜만 조회하고, 선택 날짜의 조합만 별도로 읽어 전체 이력 조회를 제거한다.
- 선택 날짜별 Meta를 API와 React Query 양쪽에서 캐시한다.

## 현재 상태
- `get_meta()`가 `fileRows`, `lineGroups`, `lineNameAvailability`를 만들면서 동일 selector를 세 번 호출한다.
- `l3_spider_daily_run_stats`의 PK는 `(date, line_id, process_id, eds_step, step_seq)`이다.
- Meta 최종 응답과 각 보조 결과에는 기존 TTL 캐시가 적용되어 있다.
- frontend는 날짜와 무관한 단일 React Query key로 `/meta`를 호출한다.

## 범위
- 수정: L3 Spider Meta 서비스의 날짜별 집계 결과 공유, selector SQL, GET query 검증, 회귀 테스트.
- 수정: L3 Spider frontend API 함수, query key, hook, page의 선택 날짜 전달.
- 유지: API 응답 구조, exclusion 규칙, line name DB 규칙, 기존 캐시 TTL.
- 제외: DB schema/migration, summary/chart 데이터 조회 계약, 화면 디자인 변경.

## 설계
- `daily_run_stats` 조합을 보관하는 공유 TTL 캐시를 두고 Meta 한 요청에서 얻은 동일 목록을 세 빌더에 전달한다.
- 빈 목록도 유효한 조회 결과로 취급해 같은 요청에서 재조회하지 않는다.
- selector는 PK 컬럼 전체를 조회하므로 `DISTINCT` 없이 동일한 결과를 반환한다.
- `/meta`는 선택적 `date=YYYY-MM-DD`를 받고, 미지정 시 완료 날짜와 빈 상세 필드를 반환한다.
- 날짜 지정 시 `WHERE date = %s`로 해당 날짜만 조회하고 조합/응답/line group 캐시 key에 날짜를 포함한다.
- React Query key에도 날짜를 포함하고 key 전환 동안 이전 응답을 placeholder로 유지한다.
- 응답 shape, migration, env, auth 계약에는 변화가 없다.

## 실행 단계
- [x] 공유 조합 조회와 Meta 빌더 전달 경로 구현
- [x] selector의 불필요한 `DISTINCT` 제거
- [x] 요청당 selector 1회 호출 및 SQL 회귀 테스트 추가
- [x] Docker Compose API 검증과 경계 감사 실행
- [x] Meta query serializer와 날짜 조건 selector 추가
- [x] 서비스 캐시와 Meta 응답을 날짜 범위로 제한
- [x] frontend API·query key·hook을 선택 날짜와 연동
- [x] backend/frontend 회귀 검증 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run l3_spider`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm --prefix apps/web run build`
- `git diff --check`

## 위험과 대응
- 위험: 개별 빌더가 전달받은 빈 목록을 cache miss로 오인해 재조회할 수 있다.
- 대응: `None`만 미전달 상태로 취급하고 빈 목록은 그대로 재사용한다.
- 위험: line name 규칙 갱신과 집계 목록 캐시의 생명주기가 달라질 수 있다.
- 대응: 기존 10분 데이터 캐시와 5초 규칙 캐시 동작을 유지하고 규칙 해석은 각 빌더에서 수행한다.
- 위험: query key가 날짜를 포함하지 않으면 다른 날짜의 Meta를 잘못 재사용할 수 있다.
- 대응: backend 캐시 key와 React Query key에 정규화된 날짜를 모두 포함한다.
- 위험: 최초 날짜 목록 응답에서 상세 선택지가 비어 잠깐 빈 화면이 보일 수 있다.
- 대응: 완료 날짜를 받은 즉시 최신 날짜를 선택하고 key 전환 중 이전 응답을 placeholder로 유지한다.

## 진행 기록
- 2026-07-13: pull 이후에도 동일 selector 3회 호출과 `DISTINCT`가 남아 있음을 확인했다.
- 2026-07-13: 공유 조합 캐시를 추가하고 Meta의 세 결과가 같은 조회 목록을 사용하도록 변경했다.
- 2026-07-13: L3 Spider 테스트 45개, Django check/migration check, backend boundary audit, diff check가 통과했다.
- 2026-07-13: 전체 이력 Meta를 완료 날짜 목록 + 선택 날짜 상세 조회로 분리하기로 결정했다.
- 2026-07-13: `/meta?date=...` 날짜 조건 조회와 backend/frontend 날짜별 캐시를 구현했다.
- 2026-07-13: L3 Spider 테스트 48개, web lint/build, Django/migration check, 양쪽 boundary audit가 통과했다.
