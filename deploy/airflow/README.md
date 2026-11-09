# Airflow 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

Worker 한 대에서 LocalExecutor와 PostgreSQL 16을 실행합니다. DAG·플러그인은 이미지에 포함하며 기본 로그인은 Keycloak입니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [서버·DB·키·연동 입력 준비](docs/01-prepare.md) |
| 2 | [chart·이미지·ODBC 준비](docs/02-artifacts.md) |
| 3 | [Keycloak 등록·검사·배포·접속 검증](docs/03-deploy.md) |
| 4 | [백업·DB 이전·DAG 갱신·장애 대응](docs/04-operations.md) |

기존 DB를 재사용할 때는 DB 비밀번호·Fernet 키를 유지합니다. 단일 Worker 구성으로 노드 장애 시 중단됩니다.
