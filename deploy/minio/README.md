# MinIO 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

MinIO는 여러 앱이 사용하는 독립 저장소입니다. 배포 설정은 `deploy/minio`, 운영 namespace는 `minio`가 소유합니다.
Portal·Airflow·Keycloak을 설치하지 않고 먼저 배포할 수 있습니다. 공용 Traefik은 먼저 준비합니다.

| 항목 | 기본값 |
| --- | --- |
| Worker | `khplanew01` |
| 콘솔 | `https://etch.samsungds.net/minio-console/` |
| 파일 공개 경로 | `https://etch.samsungds.net/minio/` |
| 앱의 S3 주소 | `http://minio.minio.svc.cluster.local:9000` |
| PVC | `minio/minio-data`, 10Gi, ReadWriteOnce |
| 입력 | `deploy/minio/env/prod.env` |

`/minio/`는 기존 브라우저 파일 경로를 유지합니다. S3 SDK와 서명 URL을 생성하는 앱은
접두사를 제거하는 공개 경로 대신 클러스터 내부의 루트 S3 주소를 사용합니다.

## 준비할 것

| 대상 | 확인할 내용 |
| --- | --- |
| 관리 호스트 | 선택 checkout의 MinIO·shared, 루트 Makefile, Bash·Make·Python 3·kubectl과 관리자 kubeconfig |
| Worker | Ready·hostname label·데이터 디스크 마운트·여유 공간·MinIO와 mc 이미지 pull 가능 여부 |
| 저장소 | 신규 local PV 또는 실제 동적 StorageClass. 기존 설치는 PV/PVC 연결·데이터 위치·계정 보존 |
| 접속 | 공용 Traefik·DNS/VIP·업무 도메인 인증서 |
| 권한 | namespace·Secret·볼륨·Job·Deployment·Ingress 생성과 신규 정적 저장소의 hostPath 준비 Job 허용 |

운영 대상과 실제 저장소는 [사내 인프라 정보](../shared/docs/infrastructure/README.md)에서 확인합니다.
이미 배포된 MinIO를 옮긴다면 [이전·재생성 조건](docs/03-operations.md)을 먼저 읽습니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업 | 완료 기준 |
| --- | --- | --- |
| 1 | [환경설정과 이미지 준비](docs/01-environment.md) | context·실제 env·이미지·저장소·관리자 계정 준비 |
| 2 | [저장소·TLS 준비·배포·검증](docs/02-deploy.md) | PVC Bound·Deployment Available·초기화 Job Complete, 콘솔 로그인과 시험 파일 업로드·다운로드 확인 |

## 운영·이전

| 하려는 일 | 문서 |
| --- | --- |
| 버킷 초기화 재시도 | [종료 Job 확인과 재시도](docs/03-operations.md#5-버킷-초기화-재시도) |
| 기존 Portal namespace에서 데이터 이전 | [이전 절차](docs/03-operations.md#6-기존-portal-namespace에서-이전) |
| 보존할 데이터가 없는 설치를 새 경로로 재생성 | [재생성 조건과 명령](docs/03-operations.md#데이터가-없는-기존-minio를-새-경로로-재생성) |
| 배포·접속 실패 | [rollout 진단](docs/02-deploy.md#4-완료-확인과-rollout-진단) |

설정·이미지 변경은 기존 데이터와 버전 호환성을 확인한 뒤 같은 env·context로 검사·재배포합니다.
