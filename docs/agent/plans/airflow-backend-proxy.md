# ExecPlan: Airflow backend proxy 전환

## 목표
- 브라우저와 Web runtime config에서 Airflow 계정 정보를 완전히 제거한다.
- 로그인한 Line Dashboard 사용자가 Django API를 통해 Airflow DAG 현황을 조회하게 한다.
- Django와 실제 Airflow 초기 관리자 계정이 profile env에서 일치하도록 검증한다.

## 현재 상태
- Web이 Airflow REST API를 직접 호출하고 Basic Auth를 브라우저에서 구성한다.
- OIDC Vite dev server에서는 non-VITE 비밀번호가 전달되지 않아 기본값에 의존한다.
- prod Web은 `AIRFLOW_PASSWORD`를 공개 `/runtime-env.js`에 기록한다.
- Airflow 초기 관리자 계정은 Compose host interpolation에 의존한다.

## 범위
- 수정: `api.drone` service/view/route/tests, Django settings, Line Dashboard Web API client, env/Compose 검증과 관련 문서.
- 제거: profile별 `web.secret.env`, Web의 Airflow URL·username·password runtime key.
- 유지: Line Dashboard 화면의 DAG overview 응답 형태와 Airflow UI 공개 경로 `/airflow`.
- 제외: DB schema/migration, Airflow 자체 인증 방식 변경, Kubernetes/Argo CD manifest.

## 설계
- Web은 `GET /api/v1/line-dashboard/airflow/dag-overview`만 Django session으로 호출한다.
- Django service는 내부 `AIRFLOW_BASE_URL`과 `api.env`의 계정으로 Airflow REST API를 호출한다.
- response는 기존 `baseUrl`, `fetchedAt`, `totals`, `dags` 형태를 유지한다.
- 개별 DAG 최근 실행 조회 실패는 해당 DAG의 `latestRun=null`로 격리하고 목록 조회 실패는 502로 반환한다.
- Airflow profile env의 `_AIRFLOW_WWW_USER_*`와 API profile env의 조회 계정이 일치하는지 서버 검증에서 확인한다.
- credential은 Web env와 `runtime-env.js` 생성 허용 목록에서 제거한다.

## 실행 단계
- [x] backend Airflow client service와 로그인 전용 view/route를 추가한다.
- [x] service/view 회귀 테스트를 추가한다.
- [x] Web API client를 Django endpoint 호출 방식으로 전환한다.
- [x] Airflow credential을 API/Airflow profile env로 이동하고 Web secret env를 제거한다.
- [x] Compose, env validator와 문서를 새 계약에 맞춘다.
- [x] backend/frontend/env/Compose 검증을 실행한다.

## 검증
- Docker Compose `api` 컨테이너에서 `api.drone.test_airflow_overview` 실행
- `docker compose ... exec -T api python manage.py makemigrations --check --dry-run`
- Web Airflow API client 단위 테스트, lint, build
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- server profile 필수값 및 API/Airflow credential 일치 검증
- backend/frontend boundary와 docs audit
- `git diff --check`

## 위험과 대응
- 위험: Airflow DAG 수만큼 최근 실행 요청이 발생해 Django 응답이 느려질 수 있다.
- 대응: 동시 요청 수를 제한한 worker pool로 최근 실행 조회를 병렬화한다.
- 위험: API와 Airflow 초기 관리자 credential이 어긋날 수 있다.
- 대응: profile 검증에서 username/password 쌍을 비교한다.
- 위험: backend 오류 형태가 기존 화면 처리와 달라질 수 있다.
- 대응: Web client가 Django 오류를 기존 `overview.error` 형태로 변환한다.

## 진행 기록
- 2026-08-29: Airflow Basic Auth를 브라우저에서 제거하고 Django proxy 방식으로 전환하기로 했다.
- 2026-08-29: 로그인 전용 Django endpoint와 bounded worker 기반 Airflow client를 추가하고 Web 직접 호출을 제거했다.
- 2026-08-29: Web secret env 3개를 제거하고 API/Airflow profile의 사용자 이름·비밀번호·trigger token 일치 검증을 추가했다.
- 2026-08-29: backend 5개, Web 5개 회귀 테스트와 migration, lint, build, env/Compose, boundary, docs 검증을 통과했다.
- 2026-08-29: OIDC/prod 기동 전 검증은 서버에서 채울 기존 OIDC/ADFS 필수값만 비어 있어 예상대로 중단된다.
