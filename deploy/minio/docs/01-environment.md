# MinIO 환경설정과 이미지 준비

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

[서버 준비](../README.md#준비할-것)를 확인한 뒤 관리 호스트의 저장소 루트에서 진행합니다. 새 Bash 터미널에서는 아래 context와 사용하는 `MINIO_ENV`를 다시 설정합니다.

## 1. 서버 입력과 이미지 준비

명령은 변경 파일이 전달된 서버의 저장소 루트에서 실행합니다.
`bash deploy/shared/scripts/checkout-server.sh minio`는 MinIO와 shared만 받습니다.

```bash
kubectl config get-contexts
read -r -p '운영 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
vi deploy/minio/env/prod.env
make server-check APP=minio PROFILE=prod
```

`MINIO_IMAGE`, `MINIO_CLIENT_IMAGE`에는 Worker에서 실제로 받을 수 있는 사내 registry의 고정 tag 또는 digest를 입력합니다.
기본 주소는 Docker Hub 사내 proxy 경로를 사용합니다. 경로와 tag가 사내 서버에서 실제로 제공되는지는 별도 확인합니다.
MinIO 서버 이미지는 Deployment, mc 이미지는 `minio-init` Job에서 사용합니다.
서버 기본값은 `bitnamilegacy/minio:2025.7.23-debian-12-r5`이며 사내 Docker Hub proxy를 경유합니다.
컨테이너는 `minio` binary를 직접 실행하고 데이터 경로 `/data`와 기동 인자를 사용합니다.
UID 0으로 실행하며 기존 볼륨의 소유권을 자동 변경하지 않습니다.
mc 기본값은 `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`를 사내 Docker Hub proxy로 가져오는 주소입니다.
두 이미지의 접근 가능 여부와 배포 대상 아키텍처를 실제 Worker에서 확인합니다.
기존 데이터가 있으면 사용 중인 버전과의 호환성·백업·복원 절차를 확인한 뒤 갱신합니다.

| 설정 | 의미 |
| --- | --- |
| `NODE_NAME` | 설치할 Worker의 hostname label |
| `IMAGE_PULL_SECRET` | minio namespace에 준비한 registry 인증 Secret, 불필요하면 빈 값 |
| `STORAGE_CLASS_NAME` | 동적 볼륨 공급자의 실제 이름. 비우면 local PV와 폴더를 자동 준비 |
| `VOLUME_NAME` | 사용할 PV 이름. 비우면 기존 PVC의 연결 이름 또는 신규 `minio-data-pv` |
| `MINIO_DATA_HOST_PATH` | 정적 모드의 Worker 저장 경로. 기본 `/appdata/minio`, 기존 PV가 있으면 실제 경로와 일치 |
| `STORAGE_SIZE` | PVC 요청 용량 |
| `INGRESS_HOST` | 업무 도메인. 인증서는 공용 Traefik에서 관리 |
| `INGRESS_TLS_SECRET` | 이전 env 호환용. 빈 값으로 유지 |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | 공용 서버 관리자 계정, 기존 운영값은 보존 |
| `MINIO_BUCKETS` | 초기 생성할 버킷의 쉼표 구분 목록, 공용 코드는 특정 앱 이름을 고정하지 않음 |

API 앱별 접근 계정은 각 앱 env에서 관리합니다. Portal은 `api.env`의 `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`를 사용합니다.
새 계정·버킷 정책은 `mc`로 실제 MinIO에 등록한 뒤 해당 앱 설정에 같은 값을 입력합니다.
버킷 목록에 이름을 추가하는 것만으로 계정이 생성되지는 않습니다.

**완료 기준:** 실제 Worker·이미지·저장소 방식·관리자 계정·버킷 목록을 정했습니다. [저장소 준비와 배포](02-deploy.md)로 진행합니다.
