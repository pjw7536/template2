# 처음 시작하기

[문서 홈](../README.md) · [개발 작업 흐름](02-usage.md) · [로컬 실행](../../local/README.md)

이 저장소는 Portal(Web·API)과 Keycloak·Airflow·MinIO·FTP·Monitoring·Headlamp를 함께 관리합니다.
작업 환경에 따라 시작 문서가 다르며, 각 문서는 해당 환경 기준으로 필요한 내용을 모두 담고 있습니다.

## 1. 시작 문서 고르기

| 하려는 일 | 시작 문서 | 완료 기준 |
| --- | --- | --- |
| 내 PC에서 Portal과 관련 서비스를 함께 실행 | [로컬 실행](../../local/README.md) | Portal 로그인과 `make k8s-smoke` 성공 |
| Portal 없이 Keycloak·Airflow 등 플랫폼만 실행 | [플랫폼 로컬 실행](../../local/01-PLATFORM.md) | `make k8s-platform-smoke` 성공 |
| 사내 서버에 설치·운영 | [서버 배포 안내](../../deploy/README.md) | 앱별 배포와 접속 확인 완료 |

로컬 실행에는 사내망이 필요하지 않으며 처음 도구·이미지·패키지를 받을 때 인터넷 연결이 필요합니다.
사내 서버는 내부 미러만 사용합니다.

## 2. 로컬 실행 후 읽을 문서

| 알고 싶은 것 | 문서 |
| --- | --- |
| 서비스 관계·폴더 구조·용어 | [아키텍처](../concepts/01-architecture.md) |
| 코드 수정 → 반영 → 검사 순서 | [개발 작업 흐름](02-usage.md) |
| 기능별 화면·권한·API | [기능별 문서](../features/README.md) |
| 환경변수 의미 | [환경 설정](../reference/01-configuration.md) |
