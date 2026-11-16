# Airflow 소스 지침

## 소유권과 경계

- `apps/airflow/**`에 적용한다. DAG는 `dags/`, 플러그인은 `plugins/`, 테스트는 `tests/`, 이미지 소스는 `image/`에 둔다. 배포 입력은 `deploy/airflow`, 개발 설정은 `local/airflow`가 소유한다.
- 업무 처리는 Portal 공개 API로 요청한다. 다른 앱의 내부 Python 모듈을 import하거나 Django 업무 로직·DB schema를 DAG에 복제하지 않는다.
- 실제 env·ODBC 설정·로그를 이미지에 복사하지 않는다.
- 서버 배포는 앱 소스 없이 실행되어야 한다. 소스 존재 검사는 이미지 빌드 시에만 수행한다.

## 검증

- DAG: `python3 -m unittest discover -s apps/airflow/tests -v`
- 이미지·배포 경로: `node --test apps/tooling/tests/airflow-deployment.test.cjs apps/tooling/tests/app-layout.test.cjs`
- 저장소 소유 경로·구조: `make audit-layout`. 다른 경계에도 영향이 있으면 해당 감사를 추가한다.
