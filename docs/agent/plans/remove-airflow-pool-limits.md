# ExecPlan: Airflow task 동시 실행 제한 제거

## 목표
- 모든 DAG의 `max_active_runs=1`은 유지한다.
- 저장소에서 추가한 `max_active_tasks`와 공용 Airflow pool 제한을 제거한다.

## 현재 상태
- Airflow DAG 7개에 `max_active_tasks`가 설정되어 있다.
- 모든 DAG task가 `shared_dag_concurrency_pool`을 사용한다.
- dev/OIDC/prod 및 단독 Airflow Compose의 `airflow-init`가 기본 3 slots 공용 pool을 생성한다.

## 범위
- 수정: `airflow/dags`, Airflow Compose, `env/airflow.common.env`, 관련 운영 문서
- 유지: DAG별 `max_active_runs`, schedule, task 의존 관계, Airflow 기본 전역 설정
- 제외: API와 Web 코드, metadata DB 복구, 운영 배포

## 설계
- DAG 생성자의 `max_active_tasks` 인자를 제거해 Airflow 기본값을 사용한다.
- 모든 operator의 명시적 `pool` 인자와 공용 pool 상수 import를 제거한다.
- 더 이상 쓰이지 않는 `airflow/dags/dag_concurrency.py`를 삭제한다.
- `airflow-init`에서 공용 pool을 생성하는 명령과 관련 환경 변수·문서를 제거한다.
- pool 인자를 생략한 task가 사용하는 `default_pool`은 Airflow의 무제한 값인 `-1` slots로 초기화한다.
- API/DB/auth contract 변경은 없다.

## 실행 단계
- [x] DAG의 task 동시 실행 제한과 공용 pool 의존성 제거
- [x] Compose/env의 공용 pool 초기화 설정 제거
- [x] 관련 운영·설정 문서 갱신
- [x] 구문, 잔여 참조, Compose 구성 검증

## 검증
- `python3 -m py_compile airflow/dags/*.py`
- 제거 대상 문자열이 실행 코드와 현재 문서에 남지 않았는지 `rg`로 확인
- 모든 DAG에 `max_active_runs=1`이 유지되는지 확인
- dev/OIDC/prod 및 단독 Airflow Compose의 config 렌더링 확인

## 위험과 대응
- 위험: 제한 제거 후 여러 DAG task가 동시에 API와 DB 부하를 높일 수 있다.
- 대응: 사용자 요청에 따라 저장소의 명시적 task 제한만 제거하고 DAG run 중복 방지 설정은 유지한다.

## 진행 기록
- 2026-07-14: `max_active_runs`를 제외한 저장소 정의 Airflow 동시 실행 제한 제거 계획을 작성했다.
- 2026-07-14: DAG 7개의 `max_active_tasks`, 공용 pool import와 task별 pool 지정을 제거했다.
- 2026-07-14: dev/OIDC/prod와 단독 Airflow Compose에서 `default_pool`을 무제한 slots인 `-1`로 초기화하도록 변경했다.
- 2026-07-14: Python 구문, Airflow DAG import, 제거 대상 잔여 참조, Compose 구성을 모두 검증했다.
