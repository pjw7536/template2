# 공용 MinIO 설치·운영

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
기본 주소는 기존 Docker Hub 사내 proxy 경로를 사용합니다. 경로와 tag가 사내 서버에서 실제로 제공되는지는 별도 확인합니다.
MinIO 서버 이미지는 Deployment, mc 이미지는 `minio-init` Job에서 사용합니다.
서버 기본값은 `bitnamilegacy/minio:2025.7.23-debian-12-r5`이며 사내 Docker Hub proxy를 경유합니다.
컨테이너는 `minio` binary를 직접 실행하고 기존 `/data`·기동 인자를 유지합니다.
기존 공식 이미지와 같은 UID 0을 명시해 기존 볼륨의 소유권을 자동 변경하지 않습니다.
mc 기본값은 `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`를 사내 Docker Hub proxy로 가져오는 주소입니다.
두 이미지의 접근 가능 여부와 배포 대상 아키텍처를 실제 Worker에서 확인합니다.
기존 데이터가 있으면 사용 중인 버전과의 호환성·백업·복원 절차를 확인한 뒤 갱신합니다.

| 설정 | 의미 |
| --- | --- |
| `NODE_NAME` | 설치할 Worker의 hostname label |
| `IMAGE_PULL_SECRET` | minio namespace에 준비한 registry 인증 Secret, 불필요하면 빈 값 |
| `STORAGE_CLASS_NAME` | 동적 볼륨 공급자의 실제 이름. 비우면 local PV와 폴더를 자동 준비 |
| `VOLUME_NAME` | 사용할 PV 이름. 비우면 기존 PVC의 연결 이름 또는 신규 `minio-data-pv` |
| `MINIO_DATA_HOST_PATH` | 정적 모드의 Worker 저장 경로. 기본 `/data/minio`, 기존 PV가 있으면 실제 경로와 일치 |
| `STORAGE_SIZE` | PVC 요청 용량 |
| `INGRESS_HOST` | 업무 도메인. 인증서는 공용 Traefik에서 관리 |
| `INGRESS_TLS_SECRET` | 이전 env 호환용. 빈 값으로 유지 |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | 공용 서버 관리자 계정, 기존 운영값은 보존 |
| `MINIO_BUCKETS` | 초기 생성할 버킷의 쉼표 구분 목록, 공용 코드는 특정 앱 이름을 고정하지 않음 |

API 앱별 접근 계정은 각 앱 env에서 관리합니다. Portal은 `api.env`의 `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`를 사용합니다.
새 계정·버킷 정책은 `mc`로 실제 MinIO에 등록한 뒤 해당 앱 설정에 같은 값을 입력합니다.
버킷 목록에 이름을 추가하는 것만으로 계정이 생성되지는 않습니다.

## 2. 저장소·namespace·인증서

```bash
kubectl --context "$KUBE_CONTEXT" get node khplanew01 -o wide
kubectl --context "$KUBE_CONTEXT" get storageclass
kubectl --context "$KUBE_CONTEXT" get pv
```

### 저장소 자동 준비

PV가 없는 새 설치는 다음 설정으로 시작합니다. `MINIO_DATA_HOST_PATH`는 실제 데이터 디스크 아래의 경로로 맞춥니다.

```dotenv
NODE_NAME=khplanew01
STORAGE_CLASS_NAME=
MINIO_DATA_HOST_PATH=/data/minio
VOLUME_NAME=
STORAGE_SIZE=10Gi
```

`make minio-up`이 namespace → Worker 저장 폴더 → 정적 PV → PVC와 MinIO 순서로 준비합니다.
신규 PV 이름은 `VOLUME_NAME` 또는 기본 `minio-data-pv`이며 `Retain`, `ReadWriteOnce`,
`minio/minio-data` 예약과 해당 Worker의 nodeAffinity를 적용합니다. PV YAML이나 Worker의 mkdir 명령을 따로 실행하지 않아도 됩니다.

폴더 준비는 같은 mc 이미지·imagePullSecret을 사용하는 일회성 Job으로 처리합니다. 신규 PV에만
hostPath `DirectoryOrCreate`를 사용하며 기존 PV에서는 `Directory`로 기존 경로의 존재와 쓰기 가능 여부를 확인합니다.
기존 파일·권한·소유권을 변경하지 않으며 기존 경로가 사라졌을 때 빈 폴더로 대체하지 않습니다.
완료된 준비 Job은 10분 후 자동 정리됩니다. 클러스터 정책상 해당 namespace의 hostPath Job 실행이 가능해야 합니다.

디스크 포맷과 마운트는 기존 노드 설정을 사용합니다. PV의 `10Gi` 선언이 새 디스크를 만들지는 않습니다.
동적 StorageClass를 지정하면 PVC만 요청하며 이 도구는 local PV나 폴더 준비 Job을 만들지 않습니다.

기존 PV가 있으면 경로·노드·용량·PVC UID를 먼저 검사하고 기존 PV 자체는 갱신하지 않습니다.
기존 PVC가 연결한 PV 이름을 우선 사용하므로 과거 PV 이름이 기본값과 달라도 유지됩니다.
기존 PV가 `Released`이거나 이전 PVC UID를 참조하거나, 연결했던 PV가 사라졌으면 자동 대체하지 않고 중단합니다.
기존 env에 새 경로 키가 없으면 `/data/minio`가 기본값입니다. 다른 경로로 운영 중이었다면
`MINIO_DATA_HOST_PATH`를 기존 PV의 `spec.local.path`에 맞춰 추가하세요.

Worker 디렉터리 준비는 [Kubernetes hostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath),
Job 정리는 [TTL-after-finished](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/) 계약을 사용합니다.

### 공용 HTTPS 인증서

업무 도메인의 인증서는 [공용 Traefik](../shared/ingress/README.md#인증서-최초-등록과-갱신)에 한 번 등록합니다.
이미 등록되어 있으면 이 단계는 생략합니다. `minio` namespace에는 TLS 인증서를 등록하지 않습니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MINIO_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MINIO_TLS_KEY
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$MINIO_TLS_CERT" TLS_KEY_FILE="$MINIO_TLS_KEY"
```

기존 Secret만 있다면 파일 대신 `TLS_SOURCE=namespace/secret`으로 가져올 수 있습니다.
인증서 갱신은 공용 등록 명령만 다시 실행합니다.

## 3. 공용 진입점과 MinIO 배포

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
make minio-check KUBE_CONTEXT="$KUBE_CONTEXT"
make minio-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

공용 진입점 명령은 MinIO용 file middleware를 반영하며 기존 VIP·배치·감시 namespace를 보존합니다.
Traefik이 재시작될 수 있으므로 기존 서비스 접속도 확인합니다.
MinIO 배포는 TLS·권한·노드·기존 저장소를 확인한 뒤 누락된 폴더·PV와 MinIO를 준비합니다.
`minio-check`는 PV가 없어도 생성 계획을 검사하고 클러스터는 변경하지 않습니다. 신규 namespace의 권한·Job admission과 실제 폴더 준비·image pull은 up에서 확인합니다.
Secret 내용은 stdin으로만 등록합니다. 기존 MinIO에 재적용하면 Secret 반영을 위해 Deployment를 재시작합니다.

`make minio-render`는 정적 모드의 PV를 포함해 env를 반영한 공개 리소스만 출력합니다. root credential은 렌더 결과에 포함하지 않습니다.
실제 설치에는 env를 읽는 `minio-up`을 사용합니다. Kustomize 경로는 구조 검사·local 공통 원본 용도입니다.
다른 env는 `MINIO_ENV=/절대경로/prod.env`로 지정합니다.

## 4. 완료 확인과 rollout 진단

```bash
kubectl --context "$KUBE_CONTEXT" -n minio get pods,pvc,ingress -o wide
kubectl --context "$KUBE_CONTEXT" -n minio get jobs -l app.kubernetes.io/name=minio-storage-prepare
kubectl --context "$KUBE_CONTEXT" -n minio logs job/minio-init
```

PVC `Bound`, Deployment `Available`, 초기화 Job `Complete`, Pod의 노드와 콘솔 로그인·업로드·다운로드를 확인합니다.
`rollout status`가 계속 대기하면 다음 명령으로 원인을 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n minio describe pods -l app.kubernetes.io/name=minio
kubectl --context "$KUBE_CONTEXT" -n minio describe pvc minio-data
kubectl --context "$KUBE_CONTEXT" -n minio get events --sort-by=.metadata.creationTimestamp
```

| 이벤트·상태 | 확인할 입력 |
| --- | --- |
| `ErrImagePull`, `ImagePullBackOff` | 실패한 전체 이미지 주소, 사내 mirror의 tag 보유·인증·CA·Worker 통신 |
| `manifest unknown`, `not found` | 해당 registry에 실제로 보관된 이미지·tag 또는 digest |
| `unauthorized`, `denied` | registry 접근 권한과 `IMAGE_PULL_SECRET` |
| 폴더 준비 Job 실패 | Job Pod Events·이미지·hostPath 정책·실제 저장 경로·쓰기 권한 |
| `FailedScheduling`, PVC `Pending` | PV·StorageClass·용량·accessModes·노드 affinity |
| `CrashLoopBackOff` | MinIO Pod 로그·쓰기 권한·디스크 상태 |

기존 설치 namespace가 `tailwind-internal`이면 진단 명령의 namespace도 그대로 사용합니다.
mc 이미지 오류는 초기화 Job 문제입니다. 서버 Deployment rollout 대기와 구분합니다.

## 5. 버킷 초기화 재시도

Job은 300초 안에 완료되어야 하며 이미 있는 버킷은 유지합니다.
기존 Job은 재배포에서 덮어쓰지 않습니다. 버킷 목록 변경·실패 재시도는 원인을 해결한 뒤
Job이 Complete 또는 Failed이고 활성 Pod가 없는 것을 확인하고 해당 Job만 삭제한 다음 `make minio-up`을 다시 실행합니다.
PVC·버킷 데이터는 삭제하지 않습니다. 실행 중인 Job을 중복 실행하지 않습니다.

## 6. 기존 Portal namespace에서 이전

새 도구는 `tailwind-internal`의 기존 MinIO Deployment 또는 PVC를 발견하면 자동 설치를 중단합니다.
namespace를 바꿔도 PVC·데이터·계정이 자동으로 이전되지 않습니다.

1. 기존 Pod·PVC·이미지·env를 기록하고 현재 rollout 문제를 먼저 해결합니다. PVC·PV는 보존합니다.
2. 앱의 쓰기를 중지하고 객체 데이터와 버킷 정책·계정·서버 설정을 별도로 백업합니다. 버전 관리·보존 정책도 확인합니다.
3. `minio` namespace에 새 볼륨과 TLS를 준비합니다. 기존 볼륨을 두 서버에서 동시에 마운트하지 않습니다.
4. 기존 `tailwind-internal/minio-console` Ingress를 파일로 보관한 뒤 제거해 새 Ingress와 중복되지 않게 합니다.
5. 준비된 이전에서만 아래 명령으로 기존 리소스 검사 예외를 명시합니다. 이 옵션도 기존 리소스를 삭제하지 않습니다.

```bash
python3 deploy/minio/scripts/manage.py check --context "$KUBE_CONTEXT" --allow-legacy
python3 deploy/minio/scripts/manage.py up --context "$KUBE_CONTEXT" --allow-legacy
```

6. 내부 Service 또는 `kubectl --context "$KUBE_CONTEXT" -n minio port-forward svc/minio 9000:9000` 경로를 통해 백업을 복원하고 파일·계정·정책을 검증합니다.
7. 각 앱의 S3 endpoint를 `http://minio.minio.svc.cluster.local:9000`으로 바꾸고 소비 앱만 갱신합니다.
8. 새 콘솔·파일 경로·앱 업로드를 확인한 뒤 쓰기를 재개합니다. 기존 PV/PVC 정리는 별도 운영 판단으로 남깁니다.

이전 준비 없이 기존 PVC를 지우거나 `kubectl delete namespace tailwind-internal`을 실행하지 않습니다.

공식 참고: [Bitnami 서버 이미지](https://hub.docker.com/r/bitnamilegacy/minio/tags),
[Bitnami client 이미지](https://hub.docker.com/r/bitnamilegacy/minio-client),
[Kubernetes 영구 저장소](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).
