# MinIO 설정과 저장소

[MinIO 가이드](../README.md) · 다음: [운영 작업](02-operations.md)

설치·업데이트 절차는 [MinIO 가이드](../README.md)에 있습니다. 이 문서는 가이드 입력의 기준, 저장소 구성, 계정 확인과 앱 계정 등록 대상, 배포 도구의 동작을 다룹니다.
이미 배포된 MinIO를 옮기거나 다시 만들려면 [운영 작업](02-operations.md)을 먼저 읽습니다.

- [준비 조건](#준비-조건)
- [이미지](#이미지)
- [저장소](#저장소)
- [root 계정 확인](#root-계정-확인)
- [앱 접근 키와 bucket 정책 등록](#앱-접근-키와-bucket-정책-등록)
- [배포 도구의 처리 내용](#배포-도구의-처리-내용)

## 준비 조건

| 대상 | 확인할 내용 |
| --- | --- |
| 관리 호스트 | 관리 호스트의 저장소 루트, Bash·Make·Python 3·kubectl과 관리자 kubeconfig |
| Worker | Ready·hostname label·데이터 디스크 마운트·여유 공간·MinIO와 mc 이미지 pull 가능 여부 |
| 저장소 | 신규 local PV 또는 실제 동적 StorageClass. 기존 설치는 PV/PVC 연결·데이터 위치·계정 보존 |
| 접속 | 공용 Traefik(앱 `ingress`)·DNS/VIP·업무 도메인 인증서 |
| 권한 | namespace·Secret·볼륨·Job·Deployment·Ingress 생성과 신규 정적 저장소의 hostPath 준비 Job 허용 |

Worker의 Ready·hostname label·taint, 기존 PV/PVC, 공용 TLS와 라우팅은 `minio-check`가 검사합니다. 데이터 디스크 마운트와 여유 공간은 [가이드의 사전 준비](../README.md#사전-준비)로 확인합니다.
운영 대상 Worker와 실제 저장소는 [사내 인프라 정보](../../shared/docs/infrastructure/README.md)에서 확인합니다.
현재 선언값은 [env/prod.env](../env/prod.env), 실제 운영 주소는 [서비스 접속 주소](../../shared/docs/infrastructure/services.md#서비스-접속-주소)에서 확인합니다. 키의 의미는 [가이드의 입력](../README.md#입력)에 있습니다.

**남은 확인:** `MINIO_SERVER_URL`이 내부 주소일 때 콘솔이 만드는 공유·presigned URL의 host가 브라우저에서 접근 가능한지 실제 콘솔에서 확인합니다. 확인 방법은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절을 따릅니다.

## 이미지

기본값은 사내 Docker Hub proxy를 경유하는 `bitnamilegacy/minio:2025.7.23-debian-12-r5`와 `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`입니다.
서버 컨테이너는 `minio` binary를 직접 실행하고 데이터 경로 `/data`를 사용하며, UID 0으로 실행하고 기존 볼륨의 소유권을 자동 변경하지 않습니다.
기존 데이터가 있으면 사용 중인 버전과의 호환성·백업·복원 절차를 확인한 뒤 이미지를 갱신합니다. 이미지 버전 변경은 [가이드 B](../README.md#b-업데이트)의 [승인] 행입니다.

두 이미지의 경로·tag 제공 여부와 대상 아키텍처는 실제 Worker에서 확인합니다. 이미지 pull은 `minio-up`에서 확인되며, 미리 확인하려면 Worker에서 받아 봅니다. Worker가 관리 호스트와 다른 노드면 관리 호스트에서 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--command`로 전달하고, `<이미지>`에는 env의 `MINIO_IMAGE`와 `MINIO_CLIENT_IMAGE` 값을 차례로 넣습니다.

[변경] Worker의 이미지 저장소에 이미지를 받습니다.

```bash
sudo -n crictl pull <이미지>
```

성공: 종료 코드 0과 `Image is up to date for` 줄. `not found`나 `manifest unknown`이면 사내 미러에 그 tag가 없는 것이므로 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절을 따릅니다.

mc 이미지 오류는 초기화·폴더 준비 Job 문제이며 서버 Deployment rollout 대기와 구분합니다.

참고: [Bitnami 서버 이미지](https://hub.docker.com/r/bitnamilegacy/minio/tags), [Bitnami client 이미지](https://hub.docker.com/r/bitnamilegacy/minio-client).

## 저장소

env의 저장소 방식을 실제 클러스터 상태와 맞춥니다.

[조회] `<NODE_NAME 값>`에는 env의 `NODE_NAME`을 넣습니다.

```bash
kubectl --context "<context>" get node <NODE_NAME 값> -o wide
kubectl --context "<context>" get storageclass
kubectl --context "<context>" get pv
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

- 기존 PV가 `/data/minio` 등 다른 경로를 쓰면 env의 `MINIO_DATA_HOST_PATH`를 실제 PV의 `spec.local.path`로 맞춥니다. 저장소의 env는 고치지 않고 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 복사본에서 이 키만 바꿔 `MINIO_ENV=<경로>`로 지정합니다. 경로가 다르면 도구는 기존 PV를 변경하지 않고 `기존 PV 경로와 MINIO_DATA_HOST_PATH가 다릅니다`로 중단합니다.
- 기존 PV가 `Released`이거나 이전 PVC UID를 참조하거나, 연결했던 PV가 사라졌으면 자동 대체하지 않고 중단합니다. [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)입니다.
- 새 경로로 전환할 때는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 먼저 수행합니다.

[조회] 기존 PV의 실제 경로를 확인합니다. `<PV 이름>`은 위 `get pv` 출력에서 `minio/minio-data`를 CLAIM으로 가진 PV입니다.

```bash
kubectl --context "<context>" get pv <PV 이름> -o jsonpath='{.spec.local.path}{"\n"}'
```

### 동적 StorageClass

`STORAGE_CLASS_NAME`을 지정하면 PVC만 요청하며 local PV나 폴더 준비 Job을 만들지 않습니다.

참고: [Kubernetes hostPath](https://kubernetes.io/docs/concepts/storage/volumes/#hostpath), [TTL-after-finished](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/), [Kubernetes 영구 저장소](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).

## root 계정 확인

`minio-up`은 실행할 때마다 env의 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`로 Secret `minio-env`를 다시 적용하고 Deployment를 다시 시작합니다. 이미 설치된 MinIO에 다른 값의 env로 배포하면 root 계정이 바뀌고, root 계정을 접근 키로 쓰는 앱의 접속이 끊깁니다. `minio-check`는 이 차이를 검사하지 않으므로 업데이트 전에 직접 확인합니다.

[조회] env의 root 계정이 운영 중인 Secret과 같은지 확인합니다. 값은 출력하지 않습니다. 저장소 밖 env를 쓰면 끝의 env 경로를 그 파일로 바꿉니다.

```bash
kubectl --context "<context>" -n minio get secret minio-env -o json | python3 -c '
import base64, json, sys
secret = json.load(sys.stdin).get("data", {})
env = dict(line.split("=", 1) for line in open(sys.argv[1]).read().splitlines() if "=" in line and not line.lstrip().startswith("#"))
for key in ("MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"):
    same = base64.b64decode(secret.get(key, "")).decode() == env.get(key)
    print(key, "일치" if same else "불일치")
' deploy/minio/env/prod.env
```

성공: 두 키 모두 `일치`. `Error from server (NotFound)`가 출력되면 Secret이 없는, 아직 설치하지 않은 상태이므로 최초 설치로 진행합니다.
`불일치`가 있으면 이 서버가 쓰는 저장소 밖 env가 있는지 [운영 위치](../../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)의 `관리 호스트 외부 앱 설정` 폴더에서 확인하고 그 경로로 다시 조회합니다. 그래도 `불일치`이면 [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)을 따릅니다. root 계정을 바꾸도록 요청받은 경우는 [가이드 B](../README.md#b-업데이트)의 [승인] 행입니다.

## 앱 접근 키와 bucket 정책 등록

앱별 접근 계정은 각 앱 env에서 관리합니다. Portal은 `api.env`의 `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`를 사용합니다.
`MINIO_BUCKETS`에 이름을 추가하는 것만으로 계정이나 정책이 생성되지는 않습니다. 버킷 목록을 바꾼 뒤의 재적용은 [가이드 B](../README.md#b-업데이트)를 따릅니다.

저장소의 현재 선언에서 Portal `api.env`의 `MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`는 MinIO env의 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`와 같은 값입니다. 이 선언대로 배포하면 Portal API는 root 계정으로 접속하므로 전용 계정을 등록하지 않아도 동작합니다. 아래 첫 행은 Portal에 전용 계정을 쓸 때 필요합니다.

| 등록 대상 | 값의 원본 | 필요한 범위 |
| --- | --- | --- |
| Portal API 전용 계정 | access key는 Portal `api.env`의 `MINIO_ACCESS_KEY`, secret key는 `MINIO_SECRET_KEY` | 버킷 `MINIO_BUCKET`(저장소 선언 `emails`) 하나. 버킷 존재 확인과 객체 읽기·쓰기·삭제. 다른 버킷과 관리 기능은 허용하지 않음 |
| 프로필 이미지 익명 읽기 | Portal `web.env`의 `VITE_MINIO_ENDPOINT`(`MINIO_API_HOST`의 HTTPS 주소) | 버킷 `profile`의 객체를 서명 없이 읽기(브라우저가 `/profile/<사용자 ID>.png`를 직접 요청). 쓰기와 목록 조회는 허용하지 않음 |

등록 도구는 MinIO client `mc`입니다. 접속 정보는 다음과 같습니다.

- 관리자 계정: env의 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`(클러스터에서는 Secret `minio-env`)
- S3 주소: `MINIO_API_HOST`의 HTTPS 루트, 또는 `kubectl --context "<context>" -n minio port-forward svc/minio 9000:9000`, 클러스터 안에서는 `http://minio:9000`
- `mc`가 있는 곳: `MINIO_CLIENT_IMAGE` 컨테이너. `minio-init` Job이 이 이미지와 Secret `minio-env`로 `http://minio:9000`에 접속합니다

**남은 확인:** 저장소에는 계정·정책을 등록하는 Make 타깃이나 Job이 없고 `mc`의 등록 명령도 정해져 있지 않습니다. 등록을 요청받으면 위 표의 대상·원본·범위와 이 사실을 보고에 담고 [pending](../../shared/docs/infrastructure/pending.md)에 남깁니다. 등록 때문에 root 계정이나 기존 버킷의 데이터를 바꾸지 않습니다.

등록 뒤에는 다음으로 확인합니다.

[조회] 프로필 이미지 익명 읽기. `<사용자 ID>`에는 프로필 이미지가 올라가 있는 사용자의 ID를 넣습니다.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://s3.etch.samsungds.net/profile/<사용자 ID>.png
```

성공: `200`. `403`이면 익명 읽기가 등록되지 않은 것입니다.

Portal 전용 계정은 그 값을 Portal `api.env`에 맞춰 Portal만 다시 배포한 뒤 파일 업로드·다운로드를 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다. 콘솔(`MINIO_BROWSER_REDIRECT_URL`) 로그인과 테스트 파일 업로드·다운로드도 같은 절의 방법으로 확인합니다.

## 배포 도구의 처리 내용

| 명령 | 영향 | 처리 내용 |
| --- | --- | --- |
| `make server-check APP=minio PROFILE=prod` | 정적 검사 | 저장소의 [env/prod.env](../env/prod.env)와 Kustomize 원본만 검사 |
| `minio-check` | 조회·server dry-run | env·노드·기존 저장소·TLS·라우팅 검사. PV가 없어도 생성 계획을 검사하며 클러스터를 변경하지 않음. 성공: `MinIO 입력·노드·저장소·TLS·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` |
| `minio-up` | 적용 | namespace·폴더·PV 준비 → Secret(stdin) → PVC·Deployment·Service → 이전 `minio-init` Job 삭제 후 다시 실행 → 라우팅 권한·Ingress. 성공: `공용 MinIO 배포 완료: <콘솔 주소>` |
| `make minio-render KUBE_CONTEXT="<context>" RENDER_OUTPUT=<폴더>` | 파일 생성(클러스터 변경 없음) | 정적 모드 PV를 포함해 env를 반영한 공개 리소스를 `<폴더>/minio.json`에 생성. root credential은 포함하지 않음 |

- Make의 `minio-check`·`minio-up`·`minio-render`는 `MINIO_ENV`를 읽습니다. 다른 env는 각 명령에 `MINIO_ENV=/절대경로/prod.env`로 지정합니다.
- 신규 namespace의 권한·Job admission과 실제 폴더 준비·image pull은 `minio-up`에서 확인됩니다. 기존 MinIO에 재적용하면 Secret 반영을 위해 Deployment를 재시작합니다.
- `minio-up`은 공용 Traefik을 설치하거나 원본으로 되돌리지 않습니다. 기존 VIP·배치·감시 namespace를 보존하면서 `minio` namespace의 라우팅 권한과 감시 범위만 추가합니다. 이때 Traefik이 재시작될 수 있습니다. Traefik 자체의 설치·갱신은 [ingress 가이드](../../shared/ingress/README.md)를 따릅니다.
- `deploy/minio/k8s` Kustomize 경로는 구조 검사·local 공통 원본 용도이며 설치에는 `minio-up`을 사용합니다.
