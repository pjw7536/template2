# ExecPlan: data_movement m_interlock

## 목표
- `data_movement/m_interlock/incoming`의 `m_interlock_<LineID>_<YYYYMMDD>_<HHMM>.csv.deflate` 파일을 PostgreSQL `m_interlock` 테이블에 `interlock_no` 기준 incremental upsert한다.
- 제공된 35개 원천 컬럼 순서, backtick 구분자, 헤더 없음, 무제한 PostgreSQL `numeric` 계약을 유지한다.

## 현재 상태
- 테이블별 loader는 `apps/api/api/data_movement/<table_name>` Django 하위 앱으로 분리되어 있다.
- 공통 파일 lifecycle은 `incoming` 파일을 `processing`으로 선점하고 성공/실패 후 삭제한다.
- Airflow DAG가 data movement trigger API를 1분마다 호출한다.
- 작업 트리에 본 요청과 무관한 미커밋 변경이 있으며 이를 수정하거나 stage하지 않는다.

## 범위
- 신규 `api.data_movement.m_interlock` 모델, migration, loader, command, 테스트를 추가한다.
- 공통 PostgreSQL COPY helper에 append 적재 연산과 무제한 `numeric` Django field를 추가한다.
- settings/env, data movement API loader registry, Airflow DAG, 운영 문서를 동기화한다.
- m_interlock 조회 API와 retention은 추가하지 않는다.

## 설계
- 파일명은 `m_interlock_<LineID>_<YYYYMMDD>_<HHMM>.csv.deflate` 정규식으로 검증한다.
- 압축 해제된 각 row는 backtick으로 분리하고 제공된 35개 컬럼에 순서대로 매핑한다.
- `usl`, `spec_target`, `lsl`, `ucl`, `cl`, `lcl`은 PostgreSQL 제약 없는 `numeric`으로 저장한다.
- `lot_id`는 원천 문자열 길이를 제한하지 않는 PostgreSQL `text`로 저장한다.
- `last_update_date`는 timezone-aware Django `DateTimeField`로 저장하며 공통 파서가 UTC로 변환한다.
- 한 파일은 transaction 내 임시 테이블로 COPY한 뒤 `interlock_no` 기준 upsert한다.
- 빈 `interlock_no` row는 제외하며 한 파일 안의 동일 key는 마지막 row를 사용한다.
- 기존 DB 중복은 `last_update_date DESC NULLS LAST`, `id DESC` 우선순위로 한 건만 남긴 뒤 `uniq_m_intlk_no` constraint를 적용한다.
- 충돌 갱신은 기존 `id`, `created_at`을 유지하고 나머지 원천 컬럼을 새 row 값으로 덮어쓴다.
- 대상 테이블에는 `id`, `created_at`을 추가하고 load-job 테이블로 파일 처리 결과를 기록한다.

## 실행 단계
- [x] 모델, migration, spec, loader, service facade, command, 테스트를 추가한다.
- [x] settings/env, API loader registry, Airflow DAG를 연결한다.
- [x] data movement API/운영/inventory/configuration 문서를 갱신한다.
- [x] Docker Compose `api` 컨테이너에서 테스트와 migration 검사를 실행한다.
- [x] backend boundary 및 문서 audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.m_interlock api.data_movement --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:docs`
- Airflow DAG source cacheless compile 검사

## 위험과 대응
- 위험: PostgreSQL 무제한 `numeric`은 Django 기본 `DecimalField`의 고정 precision/scale 계약과 다르다.
- 대응: 공통 custom field가 DB type을 `numeric`으로 명시하고 migration/schema 검증으로 확인한다.
- 위험: unique constraint 추가 시 기존 중복 데이터 때문에 migration이 실패할 수 있다.
- 대응: constraint 추가 전에 `last_update_date`, `id` 우선순위로 중복을 정리한다.
- 위험: key가 없는 row는 upsert할 수 없다.
- 대응: 빈 `interlock_no` row를 제외하고 유효 row가 하나도 없으면 파일 실패로 기록한다.
- 위험: 원천 timestamp 형식이 공통 parser 지원 범위를 벗어날 수 있다.
- 대응: 대표 형식과 null 처리 테스트를 추가하고 dry-run 경로를 제공한다.

## 진행 기록
- 2026-07-30: append-only incremental, backtick, header 없음, DDL 순서, 무제한 `numeric`, 표준 관리 컬럼 추가 계약을 확정했다.
- 2026-07-30: 신규 app/model/migration/loader/command/test와 settings/env/API/Airflow wiring을 추가했다.
- 2026-07-30: 제공된 DDL 컬럼 수를 35개로 정정하고 row별 고정 컬럼 수 검증을 추가했다.
- 2026-07-30: 신규 앱 테스트 11개와 전체 data movement 테스트 115개가 통과했다.
- 2026-07-30: migration dry-run, backend boundary audit, docs audit, diff whitespace 검사가 모두 통과했다.
- 2026-07-30: Airflow DAG는 기존 `__pycache__` 쓰기 권한 때문에 `py_compile` 대신 캐시 없는 source compile 검사로 문법을 확인했다.
- 2026-07-30: `lot_id`를 `varchar(40)`에서 길이 제한 없는 PostgreSQL `text`로 확장하고 새 migration과 장문 적재 회귀 테스트를 추가했다.
- 2026-07-30: append-only 계약을 `interlock_no` 기준 upsert로 변경하고 기존 중복 정리 migration, 빈 key 제외, 파일 내 마지막 row 우선 규칙을 추가했다.
- 2026-07-30: m_interlock 19개 및 data movement/Observer 170개 테스트, migration check/SQL, backend/frontend/docs audit를 통과했다.
