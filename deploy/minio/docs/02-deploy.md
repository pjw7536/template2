# MinIO 저장소 준비·배포·검증

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**실행 위치:** 관리 호스트의 저장소 루트입니다. [환경설정](01-environment.md)의 context·env·이미지 준비를 마친 같은 Bash 터미널에서 진행합니다. 기존 데이터 이전이나 빈 설치 재생성은 [운영 안내](03-operations.md)를 먼저 확인합니다.

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
MINIO_DATA_HOST_PATH=/appdata/minio
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
기존 PVC가 연결한 PV 이름을 우선 사용하므로 기본값과 다른 PV 이름도 유지됩니다.
기존 PV가 `Released`이거나 이전 PVC UID를 참조하거나, 연결했던 PV가 사라졌으면 자동 대체하지 않고 중단합니다.
경로 키가 없는 env에도 `/appdata/minio` 기본값을 적용합니다.
실제 저장소가 `/data/minio`라면 외부 env에 `MINIO_DATA_HOST_PATH=/data/minio` 또는 실제 PV의
`spec.local.path`를 명시해 기존 저장소를 유지하세요. 경로가 다르면 배포 도구는 기존 PV를 변경하지 않고 중단합니다.
새 경로로 전환할 때는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 먼저 수행합니다.
보존할 데이터·개별 계정·정책이 없는 설치는 [재생성 절차](03-operations.md#데이터가-없는-기존-minio를-새-경로로-재생성)를 사용할 수 있습니다.

Worker 디렉터리 준비는 [Kubernetes hostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath),
Job 정리는 [TTL-after-finished](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/) 계약을 사용합니다.

### 공용 HTTPS 인증서

업무 도메인의 인증서는 [공용 Traefik](../../shared/docs/certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)에 한 번 등록합니다.
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

설치 후 버킷 재시도·이전·재생성은 [운영 안내](03-operations.md)를 따릅니다.
