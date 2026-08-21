# ExecPlan: Airflow Compose 공통화

## 목표
- dev와 OIDC/prod가 Airflow 서비스 정의를 한 공통 Compose에서 사용한다.
- 사내 이미지 빌드와 ODBC 설정만 얇은 override로 유지한다.
- Airflow 환경 변수는 dev/server 구분 없이 `env/airflow.common.env` 하나로 관리한다.

## 현재 상태
- `compose/airflow.yml`과 `compose/airflow.internal.yml`이 PostgreSQL, init, webserver, scheduler 정의 대부분을 중복한다.
- dev는 공식 `apache/airflow:2.11.0` 이미지를 직접 사용한다.
- OIDC/prod는 사내 registry와 package mirror, BigDataQuery ODBC가 포함된 커스텀 이미지를 빌드한다.
- 작업 트리의 API env 계층 변경과 충돌하지 않도록 Airflow 범위를 분리해야 한다.

## 범위
- 수정: Airflow Compose 공통/override 구조, OIDC/prod infra include, 관련 구성 문서.
- 유지: DAG, API/auth 계약, DB schema, Airflow env key/value, dev의 public registry 접근성.

## 설계
- `compose/airflow.yml`을 유일한 Airflow 서비스 기반 정의로 사용한다.
- `compose/airflow.internal.yml`에는 사내 image/build와 ODBC mount 차이만 둔다.
- OIDC/prod infra는 Compose `include.path`의 다중 파일 병합으로 공통 파일과 internal override를 하나의 하위 모델로 불러온다.
- dev는 기존처럼 공통 파일만 include한다.
- dev/OIDC/prod Airflow는 모두 `env/airflow.common.env`만 읽는다.
- API, DB migration, auth 계약에는 영향이 없다.

## 실행 단계
- [x] Airflow internal 파일을 최소 override로 축소한다.
- [x] OIDC/prod infra include를 공통+override 병합 구조로 바꾼다.
- [x] 구성 문서에 공통/override 역할을 반영한다.
- [x] dev/OIDC/prod Compose 병합 결과를 검증한다.
- [x] Airflow dev/server env 파일과 참조를 제거하고 공통 env로 통합한다.

## 검증
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `docker compose -f docker-compose.dev.yml config --images`
- 통과: `docker compose -f docker-compose.oidc.yml config --images`
- 통과: `docker compose -f docker-compose.yml config --images`
- 확인: 병합 결과에서 dev는 public Airflow image를, OIDC/prod는 internal build와 ODBC mount를 사용하며 모든 환경은 Airflow common env만 읽는다.
- 확인: API common과 Airflow common의 `AIRFLOW_TRIGGER_TOKEN` 값이 일치한다.

## 위험과 대응
- 위험: Compose `include`는 같은 이름의 서비스를 직접 병합하지 않는다.
- 대응: 하나의 include 항목에서 `path` 목록으로 base와 override를 먼저 병합한 뒤 상위 모델에 포함한다.
- 위험: API runtime과 Airflow common의 trigger token이 달라질 수 있다.
- 대응: 서버 profile 검증에서 두 common 파일의 `AIRFLOW_TRIGGER_TOKEN` 일치를 확인한다.

## 진행 기록
- 2026-08-21: 공통 Compose와 internal override 구조로 정리하기로 결정했다.
- 2026-08-21: internal 파일을 사내 환경 차이만 담는 override로 축소하고 OIDC/prod include를 다중 파일 병합 방식으로 변경했다.
- 2026-08-21: dev/OIDC/prod Compose config와 환경별 image/env/ODBC 병합 결과 검증을 통과했다.
- 2026-08-21: 서버 profile의 빈 필수값은 추측해 채우지 않고 profile 검증에서 차단한다.
- 2026-08-21: 사용자 정정에 따라 환경별 Airflow env 파일을 제거하고 Airflow 환경 변수를 common 파일로 통합했다.
