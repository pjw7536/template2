# Airflow 소스 규칙

## 범위
- 이 규칙은 `apps/airflow/**`에 적용합니다.
- DAG는 `dags/`, 플러그인은 `plugins/`, 테스트는 `tests/`, 이미지 소스는 `image/`에 둡니다.
- 배포 입력·도구는 `deploy/airflow`, 개발 전용 설정은 `local/airflow`가 소유합니다.

## 경계
- 업무 처리는 Portal 공개 API로 요청하며 다른 앱의 내부 Python 모듈을 import하지 않습니다.
- URL·인증값은 env로 주입합니다. 실제 env·ODBC 설정·로그를 이미지에 복사하지 않습니다.
- Django 도메인 로직·DB schema를 DAG에 중복 구현하지 않습니다.
- 서버 배포는 소스 없이 동작해야 하며 소스 존재 검사는 이미지 빌드 시에만 수행합니다.

## 검증
- DAG 변경: `python3 -m unittest discover -s apps/airflow/tests -v`.
- 이미지·배포 경로 변경: `node --test apps/tooling/tests/airflow-deployment.test.cjs apps/tooling/tests/app-layout.test.cjs`.
- 저장소 구조 변경: `make audit`.
