# MinIO 설치

[앱 안내](../README.md) · 다음: [운영·이전·재생성](02-operations.md)

공용 MinIO를 `minio` namespace에 설치합니다. 모든 명령은 관리 호스트(CP1 등)의 저장소 루트, 같은 Bash 세션에서 실행합니다.
이미 배포된 MinIO를 옮기거나 다시 만들려면 [운영·이전·재생성](02-operations.md)을 먼저 읽습니다.

## 1. 준비 조건

| 대상 | 확인할 내용 |
| --- | --- |
| 관리 호스트 | CP1의 저장소 루트, Bash·Make·Python 3·kubectl과 관리자 kubeconfig |
| Worker | Ready·hostname label·데이터 디스크 마운트·여유 공간·MinIO와 mc 이미지 pull 가능 여부 |
| 저장소 | 신규 local PV 또는 실제 동적 StorageClass. 기존 설치는 PV/PVC 연결·데이터 위치·계정 보존 |
| 접속 | 공용 Traefik·DNS/VIP·업무 도메인 인증서 |
| 권한 | namespace·Secret·볼륨·Job·Deployment·Ingress 생성과 신규 정적 저장소의 hostPath 준비 Job 허용 |

운영 대상 Worker와 실제 저장소는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 확인합니다.

## 2. 서버 입력과 이미지

**목적:** context와 운영 env를 정하고 정적 검사를 통과시킵니다.

```bash
kubectl config get-contexts
read -r -p '운영 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
export MINIO_ENV="${MINIO_ENV:-$PWD/deploy/minio/env/prod.env}"
vi "$MINIO_ENV"
make server-check APP=minio PROFILE=prod
```

Make의 `minio-check`·`minio-up`·`minio-render`는 export한 `MINIO_ENV`를 읽습니다. 다른 env는 `MINIO_ENV=/절대경로/prod.env`로 지정합니다.
`server-check`는 저장소의 [env/prod.env](../env/prod.env)와 Kustomize 원본만 검사합니다. 새 Bash 세션에서는 `KUBE_CONTEXT`와 `MINIO_ENV`를 다시 export합니다.

| 설정 | 의미 |
| --- | --- |
| `NODE_NAME` | 설치할 Worker의 hostname label |
| `MINIO_IMAGE` | Deployment의 MinIO 서버 이미지. 고정 tag 또는 digest |
| `MINIO_CLIENT_IMAGE` | `minio-init` Job과 저장 폴더 준비 Job의 mc 이미지. 고정 tag 또는 digest |
| `IMAGE_PULL_SECRET` | `minio` namespace에 준비한 registry 인증 Secret, 불필요하면 빈 값 |
| `STORAGE_CLASS_NAME` | 동적 볼륨 공급자의 실제 이름. 비우면 local PV와 폴더를 자동 준비 |
| `VOLUME_NAME` | 사용할 PV 이름. 비우면 기존 PVC의 연결 이름 또는 신규 `minio-data-pv` |
| `MINIO_DATA_HOST_PATH` | 정적 모드의 Worker 저장 경로. 키가 없으면 `/appdata/minio`. 기존 PV가 있으면 실제 경로와 일치 |
| `STORAGE_SIZE` | PVC 요청 용량(`Gi`·`Ti`) |
| `MINIO_API_HOST` | S3 API 도메인 |
| `MINIO_CONSOLE_HOST` | 콘솔 도메인. `MINIO_API_HOST`와 달라야 함 |
| `MINIO_BROWSER_REDIRECT_URL` | `https://<MINIO_CONSOLE_HOST>/` 형식. 끝에 `/` 포함 |
| `MINIO_SERVER_URL` | MinIO 서버 환경변수. 검사 도구는 클러스터 내부 주소 `http://minio:9000`만 허용 |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | 공용 서버 관리자 계정. 기존 운영값은 보존 |
| `MINIO_BUCKETS` | 초기 생성할 버킷의 쉼표 구분 목록. 공용 코드는 특정 앱 이름을 고정하지 않음 |

현재 선언값은 [env/prod.env](../env/prod.env), 실제 운영 주소는 [서비스 접속 주소](../../shared/docs/infrastructure/services.md#서비스-접속-주소)에서 확인합니다.
**남은 확인:** `MINIO_SERVER_URL`이 내부 주소일 때 콘솔이 만드는 공유·presigned URL의 host가 브라우저에서 접근 가능한지 실제 콘솔에서 확인합니다.

**이미지:** 기본값은 사내 Docker Hub proxy를 경유하는 `bitnamilegacy/minio:2025.7.23-debian-12-r5`와 `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`입니다.
두 이미지의 경로·tag 제공 여부와 대상 아키텍처를 실제 Worker에서 확인합니다. 서버 컨테이너는 `minio` binary를 직접 실행하고 데이터 경로 `/data`를 사용하며, UID 0으로 실행하고 기존 볼륨의 소유권을 자동 변경하지 않습니다.
기존 데이터가 있으면 사용 중인 버전과의 호환성·백업·복원 절차를 확인한 뒤 이미지를 갱신합니다.

**앱 계정:** 앱별 접근 계정은 각 앱 env에서 관리합니다. Portal은 `api.env`의 `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`를 사용합니다.
새 계정·버킷 정책은 `mc`로 실제 MinIO에 등록한 뒤 해당 앱 설정에 같은 값을 입력합니다. 버킷 목록에 이름을 추가하는 것만으로 계정이 생성되지는 않습니다.

**기대 결과:** `server-check`가 통과하고 실제 Worker·이미지·저장소 방식·관리자 계정·버킷 목록을 정했습니다.

## 3. 저장소 준비

**목적:** env의 저장소 방식을 실제 클러스터 상태와 맞춥니다. 이 단계의 명령은 조회만 합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get node "$(sed -n 's/^NODE_NAME=//p' "$MINIO_ENV")" -o wide
kubectl --context "$KUBE_CONTEXT" get storageclass
kubectl --context "$KUBE_CONTEXT" get pv
```

### 저장소 자동 준비

PV가 없는 새 설치는 `STORAGE_CLASS_NAME=`, `VOLUME_NAME=`으로 두고 `MINIO_DATA_HOST_PATH`를 실제 데이터 디스크 아래 경로(기본 `/appdata/minio`)로 맞춥니다. `STORAGE_SIZE` 선언은 `10Gi`입니다.

`make minio-up`이 namespace → Worker 저장 폴더 → 정적 PV → PVC와 MinIO 순서로 준비합니다. PV YAML이나 Worker의 `mkdir`을 따로 실행하지 않습니다.

- 신규 PV 이름은 `VOLUME_NAME` 또는 `minio-data-pv`이며 `Retain`, `ReadWriteOnce`, `minio/minio-data` 예약과 해당 Worker의 nodeAffinity를 적용합니다.
- 폴더 준비는 같은 mc 이미지·imagePullSecret을 쓰는 일회성 Job입니다. 신규 PV에만 hostPath `DirectoryOrCreate`, 기존 PV에는 `Directory`로 존재와 쓰기 가능 여부만 확인합니다.
- 기존 파일·권한·소유권을 변경하지 않으며 기존 경로가 사라졌을 때 빈 폴더로 대체하지 않습니다. 완료된 준비 Job은 10분 후 자동 정리됩니다.
- 디스크 포맷과 마운트는 기존 노드 설정을 사용합니다. PV의 용량 선언이 새 디스크를 만들지는 않습니다.

### 기존 PV 유지

기존 PV가 있으면 경로·노드·용량·PVC UID를 먼저 검사하고 기존 PV 자체는 갱신하지 않습니다. 기존 PVC가 연결한 PV 이름을 우선 사용하므로 기본값과 다른 PV 이름도 유지됩니다.

- 기존 PV가 `/data/minio` 등 다른 경로를 쓰면 외부 env의 `MINIO_DATA_HOST_PATH`를 실제 PV의 `spec.local.path`로 맞춥니다. 경로가 다르면 도구는 기존 PV를 변경하지 않고 중단합니다.
- 기존 PV가 `Released`이거나 이전 PVC UID를 참조하거나, 연결했던 PV가 사라졌으면 자동 대체하지 않고 중단합니다.
- 새 경로로 전환할 때는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 먼저 수행합니다. 보존할 데이터·개별 계정·정책이 없으면 [재생성 절차](02-operations.md#3-데이터가-없는-기존-minio를-새-경로로-재생성)를 사용할 수 있습니다.

### 동적 StorageClass

`STORAGE_CLASS_NAME`을 지정하면 PVC만 요청하며 local PV나 폴더 준비 Job을 만들지 않습니다.

참고: [Kubernetes hostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath), [TTL-after-finished](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/).

## 4. 공용 HTTPS 인증서

**목적:** `MINIO_API_HOST`·`MINIO_CONSOLE_HOST` 두 host의 인증서를 [공용 Traefik](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)에 각각 등록합니다.
이미 등록되어 있으면 생략합니다. `minio` namespace에는 TLS 인증서를 등록하지 않습니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MINIO_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MINIO_TLS_KEY
for MINIO_TLS_KEY_NAME in MINIO_API_HOST MINIO_CONSOLE_HOST; do
  MINIO_TLS_HOST="$(sed -n "s/^${MINIO_TLS_KEY_NAME}=//p" "$MINIO_ENV")"
  make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$MINIO_TLS_HOST" \
    TLS_CERT_FILE="$MINIO_TLS_CERT" TLS_KEY_FILE="$MINIO_TLS_KEY"
done
```

기존 Secret만 있다면 파일 대신 `TLS_SOURCE=namespace/secret`으로 가져올 수 있습니다. 인증서 갱신도 이 등록 명령만 다시 실행합니다.

## 5. 공용 진입점과 MinIO 배포

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
make minio-check KUBE_CONTEXT="$KUBE_CONTEXT"
make minio-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

| 명령 | 영향 | 처리 내용 |
| --- | --- | --- |
| `ingress-check`·`ingress-up` | 조회·적용 | 공용 Traefik 준비. 기존 VIP·배치·감시 namespace를 보존하며 Traefik이 재시작될 수 있음 |
| `minio-check` | 조회·server dry-run | env·노드·기존 저장소·TLS·라우팅 검사. PV가 없어도 생성 계획을 검사하며 클러스터를 변경하지 않음 |
| `minio-up` | 적용 | namespace·폴더·PV 준비 → Secret(stdin) → PVC·Deployment·Service → `minio-init` → 라우팅 권한·Ingress |

신규 namespace의 권한·Job admission과 실제 폴더 준비·image pull은 `minio-up`에서 확인됩니다. 기존 MinIO에 재적용하면 Secret 반영을 위해 Deployment를 재시작합니다.
`tailwind-internal`에 기존 MinIO가 있으면 두 명령 모두 중단합니다. [기존 Portal namespace에서 이전](02-operations.md#2-기존-portal-namespace에서-이전)을 따릅니다.

`make minio-render`는 정적 모드 PV를 포함해 env를 반영한 공개 리소스만 출력하며 root credential은 포함하지 않습니다. `deploy/minio/k8s` Kustomize 경로는 구조 검사·local 공통 원본 용도이며 설치에는 `minio-up`을 사용합니다.

## 6. 완료 확인과 rollout 진단

```bash
kubectl --context "$KUBE_CONTEXT" -n minio get pods,pvc,ingress -o wide
kubectl --context "$KUBE_CONTEXT" -n minio get jobs -l app.kubernetes.io/name=minio-storage-prepare
kubectl --context "$KUBE_CONTEXT" -n minio logs job/minio-init
```

**기대 결과:** PVC `Bound`, Deployment `Available`, 초기화 Job `Complete`, Pod가 `NODE_NAME` Worker에 있고 콘솔 로그인·업로드·다운로드가 성공합니다.

`rollout status`가 계속 대기하면 원인을 확인합니다.

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

mc 이미지 오류는 초기화·폴더 준비 Job 문제이며 서버 Deployment rollout 대기와 구분합니다.

**다음 단계:** 실제 배치·저장소 연결을 [앱별 배치와 스토리지 선언](../../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에 기록합니다. 버킷 재시도·이전·재생성은 [운영 안내](02-operations.md)를 따릅니다.
