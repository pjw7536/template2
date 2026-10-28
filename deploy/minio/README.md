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
2026-10-28 linux/amd64에서 실제 pull·기동 후 live/ready 검사, 버킷 초기화·S3 업로드/다운로드,
공용 Traefik middleware를 통한 콘솔 HTML/JS·로그인과 파일 경로, 재시작 후 파일 보존을 검증했습니다.
서버 digest는 `sha256:6dabb4a2088c9a79908de3bc05f4586c23ad2182c8908e7e3acbf61c1467fb20`입니다.
컨테이너는 `minio` binary를 직접 실행하고 기존 `/data`·기동 인자를 유지합니다.
기존 공식 이미지와 같은 UID 0을 명시해 기존 볼륨의 소유권을 자동 변경하지 않습니다.
mc 기본값은 `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`를 사내 Docker Hub proxy로 가져오는 주소입니다.
2026-10-28 외부 원본을 linux/amd64에서 실제 pull하고 셸·mc 실행·버킷 생성 도움말·기본 설정 읽기를 검증했습니다.
확인한 digest는 `sha256:73bd39f7899a0cef12b8dd5df13aa93a3ed1aaa44236542442e9ac76819ac158`입니다.
두 이미지는 추가 업데이트가 제공되지 않는 Bitnami 보관 이미지입니다. 사내 proxy의 접근·보유 여부는 운영 Worker에서 별도로 확인합니다.
기존 `minio/mc` 이미지의 Docker Hub 태그 API는 404, manifest 조회는 인증 오류를 반환해 기본값에서 제외했습니다.
기동·파일 검증은 빈 임시 볼륨으로 수행했습니다. 기존 데이터가 있으면 사용 중인 서버 버전과 호환성을 확인하고 백업·복원 검증을 먼저 수행합니다.

| 설정 | 의미 |
| --- | --- |
| `NODE_NAME` | 설치할 Worker의 hostname label |
| `IMAGE_PULL_SECRET` | minio namespace에 준비한 registry 인증 Secret, 불필요하면 빈 값 |
| `STORAGE_CLASS_NAME` | 동적 볼륨 공급자의 실제 이름, 비우면 정적 PV |
| `VOLUME_NAME` | 정적 PV를 명시적으로 결합할 때 지정 |
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
kubectl --context "$KUBE_CONTEXT" apply -f deploy/minio/k8s/namespace.yaml
```

StorageClass를 사용하지 않으면 PV를 먼저 준비합니다. PV의 용량·accessModes·storageClassName은 PVC와 일치해야 하며,
local PV라면 실제 디스크 경로와 nodeAffinity는 `NODE_NAME`의 Worker를 가리켜야 합니다.
기존 데이터 디스크를 새 빈 저장소로 초기화하거나 다른 namespace의 PVC를 삭제하지 않습니다.

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
MinIO 배포는 TLS·권한·노드·PV 또는 StorageClass를 확인하고 MinIO만 적용합니다.
Secret 내용은 stdin으로만 등록합니다. 기존 MinIO에 재적용하면 Secret 반영을 위해 Deployment를 재시작합니다.

`make minio-render`는 env를 반영한 공개 리소스만 출력합니다. root credential은 렌더 결과에 포함하지 않습니다.
실제 설치에는 env를 읽는 `minio-up`을 사용합니다. Kustomize 경로는 구조 검사·local 공통 원본 용도입니다.
다른 env는 `MINIO_ENV=/절대경로/prod.env`로 지정합니다.

## 4. 완료 확인과 rollout 진단

```bash
kubectl --context "$KUBE_CONTEXT" -n minio get pods,pvc,ingress -o wide
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
