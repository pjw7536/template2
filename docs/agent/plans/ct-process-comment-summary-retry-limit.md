# ExecPlan: ct_process_comment summary retry limit

## 목표
- row 단위 OpenWebUI 응답 오류를 최대 3회까지만 재시도한다.
- 네트워크, HTTP, 설정 오류로 모든 대기 row가 완료 처리되지 않도록 한다.
- 재시도 한도를 소진한 row는 `update_flag='N'`으로 배치에서 제외하고 원문 변경 시 다시 처리한다.

## 현재 상태
- 요약 대상은 `update_flag='Y'` 조건으로 조회한다.
- 시간순 요약 응답 오류는 모두 실패로 반환하며 `update_flag='Y'`를 유지한다.
- 원문이 변경되면 loader가 요약을 초기화하고 `update_flag='Y'`로 변경한다.
- 핵심요약 또는 검수 응답만 비면 시간순 요약을 저장하고 완료 처리한다.

## 범위
- 수정: `ct_process_comment` model, 새 migration, loader, summary service, 관련 tests.
- 제외: Airflow DAG 구조, API 요청 contract, OpenWebUI prompt, 다른 data movement domain.

## 설계
- `summary_retry_count`, `summary_last_error_code`, `summary_last_error` 컬럼을 추가한다.
- 저장 가능한 최종 답변이 없는 OpenWebUI row 응답 오류만 재시도 횟수에 포함한다.
- 네트워크, HTTP, 설정 및 분류되지 않은 오류는 마지막 오류만 기록하고 횟수는 올리지 않는다.
- 세 번째 row 응답 오류는 `exhausted` outcome과 함께 `update_flag='N'`으로 완료한다.
- 성공 또는 원문 변경 시 재시도 상태를 초기화한다.
- 실패 상태 갱신은 `updated_at`을 변경하지 않아 기존 pending 조회 순서를 보존한다.
- API 요청 schema와 외부 설정은 변경하지 않고 세 번째 실패 outcome 상태만 `exhausted`로 반환한다.
- 핵심요약 또는 검수의 row 응답 오류는 시간순 요약을 저장하는 부분 성공으로 처리한다.
- 요약 결과와 실패 상태는 요청에 사용한 `contents_text`가 현재 값과 같을 때만 반영한다.
- API와 management command 집계에 `exhausted_count`를 포함한다.

## 실행 단계
- [x] model과 migration에 재시도 상태 컬럼 추가
- [x] loader의 원문 변경 경로에서 재시도 상태 초기화
- [x] summary service에 오류 분류, 원자적 횟수 증가, exhausted 처리 추가
- [x] service/loader 회귀 테스트 추가
- [x] Docker 기반 테스트와 migration check, backend boundary audit 실행
- [x] 핵심요약/검수 row 응답 오류의 부분 성공 처리
- [x] 원문 변경 중 이전 요청 결과 반영 방지
- [x] API/command exhausted 집계 노출 및 회귀 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.ct_process_comment api.data_movement --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm run agent:audit:api-boundary`

## 위험과 대응
- 위험: OpenWebUI 전체 장애가 row 재시도 횟수를 소진할 수 있다.
- 대응: 명시적인 최종 답변 누락 오류만 횟수에 포함하고 나머지는 기본적으로 제외한다.
- 위험: 실패 갱신이 pending 정렬을 바꿔 다른 row 처리를 지연할 수 있다.
- 대응: 실패 처리에서는 `updated_at`을 변경하지 않는다.
- 위험: 원문 변경 후 이전 실패 상태가 남을 수 있다.
- 대응: loader의 변경 row 갱신 시 세 필드를 함께 초기화한다.

## 진행 기록
- 2026-08-10: 기존 로직을 유지하는 최소 재시도 상태 설계를 확정했다.
- 2026-08-10: 세 컬럼과 migration, row 응답 오류 분류, 3회 exhausted 처리, loader 초기화를 구현했다.
- 2026-08-10: 도메인 테스트 52건, data_movement 테스트 148건, migration check와 backend boundary audit이 통과했다.
- 2026-08-10: 코드 리뷰에서 확인한 부분 성공, 원문 동시 변경, exhausted 집계 보완을 시작했다.
- 2026-08-10: 리뷰 보완 후 data_movement 테스트 153건, migration check, backend boundary audit이 통과했다.
