# ExecPlan: L3 Spider 개발환경 Mock 인덱스

## 목표
- 로컬 `docker-compose.dev.yml` 환경에서 기존 L3 Spider mock Parquet와 SQLite 인덱스로 대시보드를 실행한다.
- OIDC/prod와 기본 설정은 PostgreSQL 전용으로 유지해 mock 데이터가 운영에 노출되지 않게 한다.

## 현재 상태
- dev mount에는 `/data/l3_spider/daily_anomaly` mock Parquet와 `_meta/index.sqlite3`가 존재한다.
- mock SQLite에는 `file_index`, `daily_run_stats`, `run_status`가 모두 적재돼 있다.
- 현재 selector는 세 인덱스 테이블을 PostgreSQL에서만 조회해 로컬 DB에 테이블이 없으면 500을 반환한다.

## 범위
- 수정: L3 Spider selector의 명시적 PostgreSQL/SQLite mock source 선택.
- 수정: Django 설정, `env/api.common.env`, `env/api.local.env`, L3 Spider 설정 문서와 회귀 테스트.
- 유지: API 응답 계약, Parquet 경로, line name 규칙 DB, OIDC/prod compose 설정.
- 제외: 운영 PostgreSQL fallback, 신규 mock 생성, DB migration, frontend UI 변경.

## 설계
- `L3_SPIDER_INDEX_SOURCE`는 `postgres`와 `sqlite_mock`만 허용하고 기본값은 `postgres`로 둔다.
- `sqlite_mock`은 `L3_SPIDER_MOCK_INDEX_PATH`의 SQLite를 read-only로 조회한다.
- `env/api.local.env`만 `sqlite_mock`을 명시하며 공통·OIDC·prod는 `postgres`를 유지한다.
- selector의 공개 함수와 반환 shape는 유지하고 SQL placeholder, table name, JSON 배열 조건만 source별로 선택한다.
- mock 파일이 없거나 schema가 맞지 않으면 자동으로 PostgreSQL로 전환하지 않고 명확히 실패시킨다.

## 실행 단계
- [x] source 설정과 read-only SQLite index helper 추가
- [x] file/run/meta/trend selector를 source 중립 조회로 전환
- [x] dev env와 운영 문서 계약 동기화
- [x] SQLite mock 및 PostgreSQL selector 회귀 테스트 추가
- [x] dev API 재생성과 실제 mock endpoint 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb -v 1`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run l3_spider`
- `docker run --rm -v /home/k/template2:/workspace -w /workspace --entrypoint python template2-api scripts/agent/check_backend_boundaries.py`
- dev API에서 `meta`, `daily-summary`, `trend` mock 응답 확인
- `git diff --check`

## 위험과 대응
- 위험: 운영에서 dev flag가 잘못 주입되면 mock 데이터가 노출될 수 있다.
- 대응: 기본값과 공통 env를 `postgres`로 두고 dev env만 명시적으로 override한다.
- 위험: PostgreSQL과 SQLite의 placeholder/JSON 함수 차이로 일부 필터가 실패할 수 있다.
- 대응: source별 SQL 조각을 selector helper에서 명시하고 EQPCH/chamber 필터를 테스트한다.
- 위험: 기존 mock index schema가 현재 API 반환 계약보다 오래됐을 수 있다.
- 대응: 실제 mount의 세 테이블과 컬럼을 사전 확인하고 current `query_run_stats` 상세 shape까지 회귀 테스트한다.

## 진행 기록
- 2026-07-14: 기존 mock SQLite에서 file_index 1,776행, daily_run_stats 600행, run_status 3행을 확인했다.
- 2026-07-14: dev-only 명시 설정과 운영 PostgreSQL 고정 방식을 확정했다.
- 2026-07-14: dev API 컨테이너를 재생성하고 `meta`, `trend`, `daily-summary`의 HTTP 200 응답을 확인했다.
- 2026-07-14: L3 Spider 테스트 50개, Django check, migration check, backend boundary audit, diff check를 통과했다.
- 2026-07-14: 문서 전체 감사는 기존 inventory 누락 3건으로 실패했다. 이번 변경 문서와 무관한 `access/request`, `import_l3_spider_line_name_rules` 색인 누락이다.
