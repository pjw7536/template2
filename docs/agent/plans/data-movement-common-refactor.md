# ExecPlan: Data Movement 공통 적재 규약 표준화

## 목표
- load trigger, 파일 선점/안정성, parsing, PostgreSQL COPY, load-job 상태와 Airflow 호출 규약을 표준화한다.
- 표별 schema/적재 전략은 각 하위 계획의 명시적 policy로 보존한다.

## 현재 상태
- 공통 helper는 `file_loader`, `deflate_csv`, `streaming_csv`, `postgres_copy`, `load_command`에 나뉘며 표 loader가 outcome/job 처리와 temp COPY를 반복한다.
- API는 `{limit, dry_run}`을 받고 snake_case summary를 반환한다.
- Airflow `data_movement_file_load`가 9개 표를 호출하고 comment summary는 별도 DAG다.

## 범위
- 수정: `api.data_movement.common`, parent views/urls/tests, 9개 loader facade, Airflow DAG, env/docs.
- 유지: `/api/v1/data-movement/<table_name>/load/`, `AIRFLOW_TRIGGER_TOKEN`, incoming→processing atomic claim, 파일별 failure 기록과 처리 파일 삭제.
- 제외: 표별 schema/row filter/dedup/replace 정책 변경.

## 설계
- table registry는 table name, loader callable, policy metadata만 소유하고 parent view의 9개 직접 import/분기를 제거한다.
- request는 `{limit, dryRun}`만 허용하고 response는 `{processedCount, successCount, failureCount, outcomes}`와 outcome의 `fileName`, `rowCount`, `errorMessage`, 표별 metadata를 사용한다.
- common runner가 파일 목록→claim→job running→parse/load transaction→terminal status→file cleanup 순서를 제공한다.
- dryRun도 audit 목적의 load-job row를 남기는 현재 동작을 유지한다.
- parsing/COPY helper는 delimiter/columns/coercion을 policy argument로 받고 SQL identifier는 Django quote만 사용한다.
- 장애 fallback으로 개별 파일 실패를 outcomes에 보존하고 하나라도 실패하면 load endpoint 500을 유지한다.
- schema migration은 없으며 각 표 load-job table을 그대로 사용한다.

## 실행 단계
- [x] 9개 loader lifecycle과 API/Airflow payload characterization을 고정한다.
- [x] registry와 common runner/COPY 계약을 추가한다.
- [x] Airflow와 trigger API를 camelCase 계약으로 동시에 전환한다.
- [x] 표별 loader 연결은 정책 검증을 소유한 9개 하위 계획에서 한 번에 하나씩 수행하도록 고정한다.
- [x] trigger API 문서의 canonical request/response/status 계약을 갱신한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement`
- 9개 management command dry-run과 API token 401/200/500 contract test.
- Airflow DAG import test와 mocked trigger request snapshot.
- migration drift, backend boundary, docs audit.

## 위험과 대응
- 위험: 공통화가 표별 failure/cleanup 차이를 지운다.
- 대응: policy hook과 각 표 lifecycle characterization을 먼저 두고 common runner는 순서만 소유한다.
- 위험: Airflow가 구 snake_case body를 보내 적재가 중단된다.
- 대응: DAG와 API를 동일 배포 단위로 변경하고 stale body는 명시적 400으로 확인한다.

## 의존성과 복구
- 상위 계약: [마스터 계획](repository-refactor-master-2026-08.md). VOC 뒤에 실행하고 9개 표 앱 모두의 선행 단계다.
- 복구: 표 schema/data는 바꾸지 않으므로 Airflow body와 API/common runner를 같은 릴리스로 이전 snake_case 계약에 되돌린다. 진행 중 파일은 processing inventory 후 재큐잉한다.

## 진행 기록
- 2026-08-18: `dryRun`과 camelCase summary를 canonical 내부 API 계약으로 확정했다.
- 2026-08-18: 8단계를 완료했다. 지연 import registry와 파일 목록→선점 runner를 추가하고 load/summary trigger 및 두 Airflow DAG를 camelCase로 동시에 전환했다. legacy `dry_run`은 400으로 고정했으며 Data Movement 159개·Airflow 3개 테스트, Django check와 migration drift 검사를 통과했다. 표별 parse/job/transaction/cleanup은 정책 유실을 막기 위해 각 하위 계획이 연결을 소유한다.
