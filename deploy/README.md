# 서버 배포

사내 Kubernetes 클러스터에 준비된 이미지·chart로 앱을 설치·운영하는 안내입니다.
명령은 관리 호스트(CP1)의 저장소 루트에서 실행합니다.

## 처음 준비하는 순서

1. [서버 파일 받기](shared/docs/operations/01-checkout.md): CP1에 저장소를 clone하고 갱신합니다.
2. [배포 준비와 검증](shared/docs/operations/02-deploy.md): context·공용 Ingress·env·TLS를 준비하고 앱 순서를 확인합니다.
3. 아래 앱별 안내에서 설치를 진행합니다.
4. [운영과 문제 해결](shared/docs/operations/03-operations.md)으로 갱신·장애·백업을 관리합니다.

대상 서버·주소·적용 상태는 [사내 인프라 정보](shared/docs/infrastructure/README.md)와 실제 조회를 대조합니다.
서버에서 아직 적용·확인해야 하는 작업은 [서버 적용 대기 작업](shared/docs/infrastructure/pending.md)에 모여 있습니다.
공개 도메인은 [서비스 주소](shared/docs/infrastructure/services.md#공개-도메인과-인증), DNS·VIP·인증서는 [네트워크](shared/docs/infrastructure/network.md)가 원본입니다. DNS 변경은 사용자가 수행합니다.

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

클러스터·HTTPS·인증서·배포·운영 절차는 [공통 배포 절차](shared/docs/README.md)에서 선택합니다.
