# 서버 배포

명령은 관리 호스트의 저장소 루트에서 실행합니다.
처음 준비할 때는 [서버 파일 받기](shared/docs/operations/01-checkout.md) → [공통 준비·배포](shared/docs/operations/02-deploy.md) → 앱 안내 순서로 진행합니다.
대상 서버·주소·적용 상태는 [인프라 원본](shared/docs/infrastructure/README.md)과 실제 조회를 대조합니다.

## 앱별 배포와 상세 작업

| 앱 | 설치·운영 안내 |
| --- | --- |
| Keycloak | [인증 서버·사내 로그인](keycloak/README.md) |
| MinIO | [공용 객체 저장소](minio/README.md) |
| Airflow | [워크플로 실행](airflow/README.md) |
| Monitoring | [지표 수집·Grafana](monitoring/README.md) |
| Headlamp | [Kubernetes 관리 화면](headlamp/README.md) |
| FTP | [노드별 파일 수신](ftp/README.md) |
| Portal | [업무 포털](portal/README.md) |

## 공통 작업

[클러스터·HTTPS·인증서·배포·운영 절차](shared/docs/README.md)에서 필요한 작업을 선택합니다.
설치 후에는 rollout뿐 아니라 실제 접속·로그인·업무 동작을 확인합니다.

서버 실행에는 선택한 `deploy/<app>`과 `deploy/shared`, 루트 Makefile을 사용합니다.
이미지를 직접 빌드할 때만 앱 소스를 추가합니다. 외부 PC 개발은 [local 안내](../local/README.md)를 따릅니다.
