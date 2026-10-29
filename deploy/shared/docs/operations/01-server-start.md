# 서버 앱 준비·기동 순서

[배포 안내](../../../README.md) · [앱별 배포](../kubernetes/05-applications.md)

서버는 준비된 이미지·배포 정의·실제 env를 사용해 앱별로 검사하고 기동합니다.
명령은 배포 호스트의 저장소 루트에서 실행합니다. 서버용 선택 checkout만으로 진행할 수 있습니다.

## 준비 순서

| 순서 | 할 일 | 실행할 절차 |
| --- | --- | --- |
| 1 | 담당 앱의 배포 파일 받기 | [선택 checkout](../../../01-SERVER_CHECKOUT.md) |
| 2 | 대상 노드·스토리지·진입점 확인 | [클러스터 구성과 상태 확인](../infrastructure/cluster.md), [Traefik 셋업](../kubernetes/02-traefik.md) |
| 3 | 앱별 이미지·chart·DB·env·인증서 준비 | [환경설정](../configuration/environment.md), 각 앱의 설치 안내 |
| 4 | 인증·저장소 등 의존 서비스 준비 | [Keycloak](../../../keycloak/README.md), [MinIO](../../../minio/README.md) |
| 5 | 필요한 앱만 검사·기동 | 아래 앱별 실행 안내 |
| 6 | 접속·로그인·업무 동작 확인 | [완료 확인](../kubernetes/06-verification.md) |

## 앱별 실행 안내

| 앱 | 검사·기동의 원본 |
| --- | --- |
| Keycloak | [서버 준비](../../../keycloak/01_SERVER_SETUP.md) → [로그인 설정](../../../keycloak/04_SETUP_FLOW.md) |
| Airflow | [서버 준비](../../../airflow/01_SERVER_SETUP.md) → [검사·배포·접속](../../../airflow/04_SETUP_FLOW.md) |
| MinIO | [설치·저장소 준비·배포](../../../minio/README.md) |
| Portal | [입력 준비](../../../portal/README.md) → [운영 overlay](../../../portal/k8s/overlays/prod/README.md) |
| Monitoring | [설정·chart·검사·배포](../../../monitoring/README.md) |
| Headlamp | [설치 순서와 로그인 검증](../../../headlamp/README.md) |
| FTP | [서버 설치](../../../ftp/01_SERVER_SETUP.md) → [접속 확인](../../../ftp/02_OPERATIONS.md) |

앱마다 노드·디스크·DB 입력을 확인합니다. Airflow 업무 DAG가 Portal을 호출한다면 해당 Portal API도 준비해야 합니다.
Portal은 DB migration·Keycloak client 등록을 마친 뒤 API·Web을 기동합니다.
파일 검사 통과 후 실제 클러스터의 rollout과 접속 결과를 확인해야 설치를 마친 것입니다.

## 설정 변경 후 반영

Git 갱신만으로 실행 중인 앱이 바뀌지는 않습니다.
이미지 변경은 해당 앱의 이미지 태그와 배포를 갱신하고, env·인증서 변경은 해당 앱의 적용 절차를 따릅니다.
공통 파일 관리는 [CP1 운영](02-cp1.md)을 참고합니다.
