# Portal 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

API·Web·edge-nginx를 배포합니다. 외부 PostgreSQL·Keycloak·공용 MinIO와 필요한 업무 파일 저장소를 먼저 준비합니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [환경설정·Keycloak 등록·migration·배포·기능 검증](docs/01-install.md) |
| 2 | [최초 운영자·앱 역할·데이터 권한](docs/02-access.md) |
| 3 | [env·Secret 반영·재시작·health 확인](docs/03-operations.md) |

기존 DB 갱신은 쓰기 중지·백업·사전 검사·migration·사후 검사를 거친 뒤 앱을 재개합니다.
