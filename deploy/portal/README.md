# Portal 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

Portal의 API·Web·edge-nginx와 운영 Kubernetes overlay를 관리합니다.
Keycloak·공용 MinIO와 Portal 전용 외부 PostgreSQL을 먼저 준비합니다.
운영 입력은 `env/prod/`, 자동 테스트 입력과 CI Compose는 `env/test/`·`compose/test.yml`이 소유합니다.

## 준비할 것

| 대상 | 확인할 내용 |
| --- | --- |
| 배포 파일 | Portal 선택 checkout. 기반 앱 파일을 유지하며 추가할 때는 `all`로 확장 |
| 관리 도구 | Bash·Make·kubectl, 대상 클러스터 kubeconfig와 namespace·Secret·Job·앱 리소스 적용 권한 |
| 이미지 | 실제 registry의 API·Web 고유 태그와 pull 인증. migration도 같은 API 이미지 사용 |
| DB | Portal 전용 외부 PostgreSQL의 DB·계정·접속과 `pg_trgm` extension. Keycloak DB와 별개 |
| 로그인 | Keycloak의 Realm·사내 로그인 준비. Portal client는 Portal 입력으로 등록 |
| 파일 저장소 | 공용 MinIO의 실제 접근 계정·bucket 권한과 필요한 업무 파일 PVC |
| 공개 접속 | 공용 Traefik·DNS/VIP·Portal 도메인 인증서 |

노드·연결 경로는 [사내 인프라 정보](../shared/docs/infrastructure/README.md)에서 찾고 실제 클러스터를 조회합니다.
[overlay 입력](k8s/overlays/prod/README.md)의 이미지·스토리지 placeholder를 실제 값으로 바꿔야 합니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업 | 완료 기준 |
| --- | --- | --- |
| 1 | [환경설정](docs/01-environment.md)·[overlay 입력](k8s/overlays/prod/README.md) | API·Web·client 검사 통과, 이미지·영속 저장소 확정 |
| 2 | [SSO·client 등록 절차](docs/02-sso.md) | 전용 client 입력·등록 전제·검증 방법 확인. 실행은 배포 절차의 지정 단계에서 수행 |
| 3 | [배포·migration·검증](docs/03-deploy.md) | client 등록·Secret·migration 사후 검사·앱·라우팅 적용, health·로그인·파일 동작 확인 |
| 4 | [최초 운영자와 사용자 권한](docs/04-access.md) | 운영자·내부·제한 사용자의 허용·거부 확인 |

실행 명령은 배포 절차의 순서를 따릅니다. client 등록은 namespace 준비 등 해당 안내의 전제를 확인합니다.
기존 DB 갱신에서는 쓰기 중지·백업·사전 검사·사후 검사를 생략하지 않습니다.

## 운영·참고

| 하려는 일 | 문서 |
| --- | --- |
| env 변경과 Secret·Pod 반영 | [운영 안내](docs/05-operations.md) |
| Portal client 등록·변경 | [SSO·client 등록](docs/02-sso.md) |
| 기존 권한 방식에서 전환 | [권한 전환](docs/04-access.md#기존-부서-기반-권한에서-전환) |
| MinIO 설치·버킷 재시도·이전 | [공용 MinIO](../minio/README.md) |
| 외부 PC 개발 | [local 안내](../../local/README.md), 전체 개발 checkout에서 사용 |
