# ExecPlan: account migration 상태 복구

## 목표
- 개발 DB의 실제 account schema/data 상태와 Django migration 이력을 일치시킨다.
- account 데이터 삭제나 적용된 migration 파일 수정 없이 표준 API startup을 복구한다.

## 현재 상태
- 복구 전 `account.0001`부터 `0005`까지와 삭제된 예전 `0006~0008` 이름이 적용 이력에 남아 있었다.
- 복구 후 현재 graph의 `0006_account_authorization_system`까지 적용 완료로 표시된다.
- 실제 `account_affiliation`에는 `0006`이 추가하는 `uniq_acc_aff_usr_sdw_ci`, `chk_acc_aff_usr_sdw_trim`, `is_active`가 이미 존재한다.
- `0006`이 제거하려는 `uniq_acc_aff_usr_sdw_prd`는 실제 DB에 없다.
- 소속 데이터 12건에는 대소문자·공백 기준 중복, 빈 값, 앞뒤 공백이 없다.
- 표준 API entrypoint는 `0006`을 다시 실행하면서 이미 없는 옛 constraint 삭제 단계에서 중단된다.

## 범위
- 수정할 영역
  - 로컬 개발 PostgreSQL의 `django_migrations` account 적용 이력
  - 복구 과정과 검증 결과를 기록하는 이 ExecPlan
- 수정하지 않을 영역
  - account 업무 데이터 삭제/초기화
  - 기존 migration 파일 수정
  - 운영/OIDC DB
  - account business rule 또는 API contract

## 설계
- 먼저 `0006`이 요구하는 컬럼, 테이블, index, constraint, 데이터 정규화 결과를 전부 읽기 전용으로 검증한다.
- 실제 DB가 `0006` 최종 상태와 일치할 때만 `migrate account 0006 --fake`로 이력 한 건을 보정한다.
- schema/data가 일부라도 누락되면 fake하지 않고 누락 항목과 안전한 복구 방법을 다시 판단한다.
- 복구 후 임시 recovery 컨테이너를 종료하고 표준 Compose API를 정상 entrypoint로 시작한다.

## 실행 단계
- [x] 실패 migration과 실제 affiliation constraint를 확인한다.
- [x] `0006` 전체 schema/data 결과가 반영됐는지 검증한다.
- [x] 누락된 grant 2개와 constraint 2개를 동일 migration 정의로 보충한다.
- [x] 검증 통과 후 `account.0006`을 fake 적용한다.
- [x] 표준 API startup과 health를 확인한다.
- [x] migration/tests 결과와 최종 컨테이너 상태를 기록한다.

## 검증
- 통과: `python manage.py showmigrations account`
  - 현재 graph의 `0001~0006` 전체 적용
- 통과: account 관련 테이블의 column/index/constraint introspection
- 통과: affiliation/role/status/data-scope 무결성 SQL
  - 중복·공백·잘못된 상태·누락 grant 모두 0건
- 완료: `python manage.py migrate account 0006 --fake`
- 통과: `python manage.py migrate --check`
- 통과: `python manage.py makemigrations --check --dry-run`
- 통과: `python manage.py check`
- 통과: Account 전체, TTTM 전체, auth policy 회귀 테스트 (235 tests)
- 통과: `npm run agent:audit:api-boundary`
- 통과: 표준 API `/api/v1/health/` HTTP 200

## 위험과 대응
- 위험: `0006` data migration 일부가 실제로 실행되지 않았을 수 있다.
- 대응: scope 설정, grant 복제, role/status 정규화 결과를 fake 전에 검증한다.
- 위험: schema가 일부만 앞서 있으면 fake 후 Django state와 DB가 계속 어긋날 수 있다.
- 대응: `0006`의 모든 신규 column/table/index/constraint 이름을 introspection으로 확인한다.
- 위험: 잘못된 DB를 대상으로 migration 이력을 바꿀 수 있다.
- 대응: 현재 dev Compose DB alias와 database name을 출력하고 운영/OIDC DB는 건드리지 않는다.

## 진행 기록
- 2026-07-30: `account.0006`이 미적용으로 기록됐지만 affiliation의 주요 `0006` schema가 이미 존재함을 확인했다.
- 2026-07-30: 소속 12건에 정규화 중복, 빈 값, 앞뒤 공백이 없음을 확인했다.
- 2026-07-30: DB에는 삭제된 예전 migration 이름 `0006_affiliation_access_integrity`, `0007_app_affiliation_data_scope`, `0008_affiliation_identifier_format`이 적용돼 있고 현재 통합 `0006` 기록만 없음을 확인했다.
- 2026-07-30: 통합 `0006` 최종 상태 비교에서 누락된 앱별 grant 2개와 `UserSdwtProdChange` constraint 2개만 확인했다.
- 2026-07-30: 통합 migration의 idempotent data 함수로 grant를 보충하고 Django schema editor로 constraint를 추가한 뒤 전체 schema/data 불변조건을 재검증했다.
- 2026-07-30: 최종 상태가 일치한 뒤 통합 `0006`을 fake 적용해 migration ledger를 현재 graph와 맞췄다.
- 2026-07-30: 임시 recovery 컨테이너를 제거하고 표준 Compose API를 복구했다. migration pending 없음, account 224개 테스트 통과, health HTTP 200을 확인했다.
