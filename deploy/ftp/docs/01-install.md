# FTP 설치 준비와 별도 overlay 배포

[FTP 가이드](../README.md) · [접속 확인과 운영](02-operations.md)

설치·업데이트 절차는 [FTP 가이드](../README.md)에 있습니다. 이 문서는 배포 전에 확인하는 노드·계정·env 입력의 상세와, 가이드의 배포 명령 대신 쓰는 별도 overlay 배포 방법입니다.

- [노드·계정 준비](#노드계정-준비): 대상 노드 선택, 각 노드의 디스크·포트·방화벽, 계정 파일
- [배포 env와 도구 동작](#배포-env와-도구-동작): env 키, 각 타깃이 하는 일
- [별도 overlay 배포](#별도-overlay-배포): 이미지·경로·패치를 직접 관리할 때 가이드의 배포 명령 대신 사용

## 노드·계정 준비

### 1. 실행 위치와 준비물

| 위치 | 필요한 작업 |
| --- | --- |
| 관리 호스트 | 저장소 checkout, Python 3.10+·Make·Bash·kubectl, kubeconfig. 검사·배포 실행 |
| FTP를 실행할 각 Linux 노드 | Kubernetes 등록, 저장 디스크·기존 파일 권한·포트 확인 |
| FTP 클라이언트 PC | 대상 노드 IP로 접속할 네트워크·FTP 클라이언트 |

kubectl에는 노드 조회·라벨 변경, namespace·Secret·DaemonSet·ConfigMap 적용과 Pod 조회 권한이 필요합니다.
각 대상 노드에서는 디스크·포트만 확인하고, 검사·배포는 관리 호스트에서 한 번 실행합니다.

### 2. 클러스터와 대상 노드 선택

[조회] 관리 호스트의 저장소 루트에서 후보 노드와 이미 FTP 라벨이 붙은 노드를 확인합니다.

```bash
kubectl config get-contexts
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true -o wide
```

[사람] 대상 노드를 정해 `FTP_NODES` 값으로 전달합니다.

- `FTP_NODES`에는 노드 목록의 `NAME` 값을 `worker-a` 또는 `worker-a,worker-b`처럼 넣습니다. 노드별로 명령을 반복하지 않습니다.
- 값을 지정할 때는 이미 FTP 라벨이 붙은 노드까지 포함한 **전체 목록**을 넣습니다. 기존 노드를 빼면 검사에서 중단하므로, 노드 제거는 [특정 노드에서 중단](02-operations.md#4-특정-노드에서-중단)을 먼저 수행합니다.
- `FTP_NODES`를 비우면 이미 `etch.io/ftp-enabled=true` 라벨이 있는 노드를 그대로 사용합니다. 라벨이 있는 노드가 없는 최초 설치에는 대상 노드를 지정해야 합니다.
- 후보 노드의 이름·IP·용도는 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)에서 확인하고 위 조회 결과와 대조합니다. 서버 목록은 FTP 배포 완료 목록이 아닙니다.

검사는 Linux·Ready 상태, cordon·차단 taint, IPv4 InternalIP를 확인합니다.

#### Control plane도 대상에 추가하기

[env/prod.env](../env/prod.env) 또는 사용 중인 `FTP_ENV` 파일의 `FTP_ALLOW_CONTROL_PLANE`이 허용 여부입니다. 기본값과 키를 생략한 값은 `true`이며, 막으려면 `false`로 지정합니다.
`FTP_NODES`에 control plane의 실제 노드 이름을 명시해야 배포 대상이 됩니다.
FTP Pod는 control-plane·master 역할의 `NoSchedule` taint만 허용합니다. 역할 라벨·taint를 제거하지 않으며, 다른 `NoSchedule`·모든 `NoExecute`, cordon·NotReady는 계속 차단합니다.
[별도 overlay 배포](#별도-overlay-배포)에서는 [control plane toleration 패치](#control-plane을-포함하는-수동-overlay)를 함께 추가합니다.

### 3. 각 노드의 저장 폴더와 포트 확인

선택한 **각 노드**에 SSH로 접속해 실행합니다. control plane을 포함했다면 해당 노드도 확인합니다.

```bash
hostname
ip -br address
if [[ -d /appdata/data_movement ]]; then
  df -h /appdata/data_movement
  sudo stat -c '%U:%G %a %n' /appdata/data_movement
else
  # 저장 폴더는 Pod 배포 시 생성합니다. 사용할 디스크의 여유를 확인합니다.
  df -h /appdata 2>/dev/null || df -h /
fi
sudo ss -lntp | grep -E ':(6380|8076|8077|8078|8079)[[:space:]]' || true
```

**기대 결과와 조치:**

- 저장 폴더: `hostPath.type=DirectoryOrCreate`로 kubelet이 없는 `/appdata/data_movement`를 0755로 생성합니다. 수동 `mkdir`은 필요하지 않습니다.
  FTP 시작 시 최상위 폴더 소유자만 이미지의 `ftp:ftp`로 바꾸며 하위 파일 소유권은 변경하지 않습니다.
- 기존 데이터: 기존 파일은 해당 노드의 `/appdata/data_movement`로 이관하고 읽기·쓰기 권한을 맞춥니다.
  기존 `/data/data_movement`를 사용하던 노드는 [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 먼저 수행합니다. 그대로 배포하면 새 빈 폴더를 사용하므로 파일 복사와 소비 앱의 호스트 경로 연결을 먼저 확인합니다.
- 포트: 위 `ss` 결과가 비어 있어야 합니다. 기존 FTP가 포트를 쓰고 있으면 전환 시 중단합니다.
- 소비 앱: 파일은 접속한 노드에만 저장되므로 Airflow·Portal이 읽을 위치도 함께 결정합니다.

방화벽은 **파일 전송 클라이언트의 허용 IP/CIDR → 선택한 각 FTP 노드 InternalIP**로 요청합니다. APP VIP의 443과 별개이며 호스트 방화벽과 중간 네트워크 방화벽을 모두 확인합니다.

| 목적지 TCP 포트 | 용도 | 확인 |
| --- | --- | --- |
| `6380` | FTP 로그인·제어 연결 | 로그인 성공 |
| `8076–8079` | Passive 목록 조회·파일 전송 | 목록·업로드·다운로드 성공 |

### 4. 관리 호스트의 계정 파일 준비

새 설치는 준비된 계정 파일 `deploy/ftp/env/initial-account.env`를 그대로 사용하므로 따로 할 일이 없습니다. `FTP_CREDENTIAL_FILE`을 지정하지 않으면 이 파일을 사용합니다.
이미 FTP가 운영 중이어서 계정이 다르거나 다른 파일을 쓸 때만 아래 형식으로 준비하고, 배포·검사 명령에 `FTP_CREDENTIAL_FILE=<계정 파일 절대 경로>`를 붙입니다.

- 파일에는 `FTP_USER`와 `FTP_PASS`를 각각 한 번만 `KEY=value`로 기록합니다. 값에 `export`나 감싸는 따옴표를 넣지 않습니다. 형식 예제는 [credentials.env.example](../credentials.env.example)입니다.
- 사용자 이름에는 영문·숫자·밑줄·하이픈만 사용합니다. 비밀번호는 비워 두지 않으며 줄바꿈·역슬래시를 넣지 않습니다.
- 파일 권한이 넓으면 도구가 소유자 전용(0600)으로 좁힙니다. 좁힐 수 없으면 오류로 멈추므로 파일 소유자를 확인합니다.
- 모든 대상 노드는 `etch-ftp/ftp-credentials` Secret을 공유합니다. `ftp-up`은 Secret이 없을 때만 이 파일로 만듭니다.
- 기존 Secret이 계정 파일과 다르면 검사가 변경 전에 중단합니다. 기존 계정 파일을 사용하거나 [계정 변경](02-operations.md#5-계정-변경)을 따릅니다.

## 배포 env와 도구 동작

`ftp-check`·`ftp-up`은 [env/prod.env](../env/prod.env)를 읽어 아래 키를 적용합니다. 다른 키나 중복 키가 있으면 검사가 멈춥니다.

| 키 | 의미와 형식 |
| --- | --- |
| `FTP_IMAGE` | 사내 Docker Hub 미러의 이미지 주소(원본 digest 고정). 고정 tag 또는 sha256 digest가 있어야 하고 `latest`와 `http://`·`https://` 접두는 쓸 수 없음. 다른 경로·digest가 필요하면 실제 주소로 바꾸고, 사내 미러의 해당 digest 제공 여부·접근·CA는 Worker에서 확인 |
| `IMAGE_PULL_SECRET` | registry 인증이 필요할 때 `etch-ftp` namespace에 미리 만든 pull Secret 이름. 빈 값이면 추가하지 않음 |
| `FTP_ALLOW_CONTROL_PLANE` | `true` 또는 `false`. [Control plane 선택](#control-plane도-대상에-추가하기) 참조 |

별도 env 파일은 각 명령에 `FTP_ENV=/절대/경로/ftp.env`를 붙여 지정합니다. 이미지 설정 env와 FTP 로그인 계정 파일은 별개입니다.

각 타깃이 하는 일입니다. 실행 순서와 명령은 [가이드](../README.md#a-최초-설치)에 있습니다.

| 타깃 | 영향 | 처리 내용 |
| --- | --- | --- |
| `server-check` | 조회 없음 | `k8s/start.sh` 문법과 Kustomize 원본 렌더. `make server-check APP=ftp PROFILE=prod`로 실행 |
| `ftp-check` | 클러스터 조회만 | 이미지 설정·선택 pull Secret 존재, 계정 형식·권한, 원본 렌더, 대상 노드 상태, 기존 Secret 일치 여부 |
| `ftp-up` | 적용 | 같은 검사 → 없는 namespace 생성 → 없는 Secret 생성 → 노드 라벨 → 스택 적용 → 최대 5분 기동 대기 → Pod 위치 출력. `FTP 배포 완료`로 끝남 |
| `ftp-smoke` | 클러스터 조회와 연결 시험 | 관리 호스트에서 FTP Pod가 실행 중인 각 노드의 6380 연결. 전송 요청이 있을 때만 열리는 passive 포트는 보지 않음 |

- 검사 통과는 이미지 pull·원격 디스크·방화벽·실제 FTP 인증 성공을 보장하지 않습니다. [문제 해결](02-operations.md#6-문제-해결)을 확인합니다.
- 배포 중 실패하면 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 재실행합니다. 재실행은 파일 데이터를 삭제하지 않습니다.
- `kubectl apply -k deploy/ftp/k8s`를 직접 실행하면 env가 적용되지 않아 공개 이미지를 사용하고 control plane toleration도 추가되지 않습니다. 직접 적용이 필요하면 아래 별도 overlay 배포를 사용합니다.

## 별도 overlay 배포

이미지·저장 경로·추가 패치를 Git 밖 overlay로 관리할 때 가이드의 배포 명령 대신 사용합니다. 두 배포 방식을 함께 실행하지 않으며, overlay 운영 중에는 `make ftp-up`을 사용하지 않습니다.
env와 overlay는 자동으로 합쳐지지 않습니다. overlay의 이미지·pull Secret·toleration은 아래 입력으로 직접 지정합니다. overlay 작성 → 검사와 렌더 확인 → 적용 순서로 진행합니다.

**준비물:** [노드·계정 준비](#노드계정-준비) 완료, 승인된 사내 registry에서 **실제로 확인한** `fauria/vsftpd` 이미지 경로와 digest. 원본 digest를 그대로 쓰려면 사내 registry에서도 같은 digest로 조회되는지 확인합니다.

기본 경로가 다른 서버는 같은 목적의 경로를 준비하거나, 별도 overlay에서 hostPath와 노드 선택 라벨·DaemonSet 이름을 함께 변경해 서로 겹치지 않는 노드 그룹으로 배포합니다.

### Git 밖에 overlay 작성

관리 호스트의 저장소 루트에서 실행합니다. `FTP_IMAGE_REPOSITORY`는 태그·digest 없는 registry/이미지 경로, `FTP_IMAGE_DIGEST`는 `sha256:...`, `FTP_OVERLAY_DIR`는 Git 밖의 **새 디렉터리 절대 경로**입니다. 기존 overlay가 있으면 이 단계를 반복하지 않고 저장된 경로를 사용합니다.

```bash
FTP_IMAGE_REPOSITORY="<사내 FTP 이미지 경로(태그·digest 제외)>"
FTP_IMAGE_DIGEST="<사내에서 확인한 이미지 digest(sha256:...)>"
FTP_OVERLAY_DIR="<새 FTP overlay 디렉터리 절대 경로>"
FTP_BASE_DIR="$(pwd)/deploy/ftp/k8s"
(
  set -euo pipefail
  [[ "$FTP_OVERLAY_DIR" = /* ]]
  [[ -n "$FTP_IMAGE_REPOSITORY" && "$FTP_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
  umask 077
  mkdir -m 700 "$FTP_OVERLAY_DIR"
  FTP_BASE_REF="$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$FTP_BASE_DIR" "$FTP_OVERLAY_DIR")"
  cat > "$FTP_OVERLAY_DIR/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: etch-ftp
resources:
  - "$FTP_BASE_REF"
images:
  - name: fauria/vsftpd
    newName: "$FTP_IMAGE_REPOSITORY"
    digest: "$FTP_IMAGE_DIGEST"
patches:
  - target:
      kind: Namespace
      name: etch-ftp
    patch: |-
      apiVersion: v1
      kind: Namespace
      metadata:
        name: etch-ftp
      \$patch: delete
EOF
)
```

- Namespace 제외 패치는 렌더 결과에서만 Namespace를 뺍니다. 클러스터의 Namespace를 삭제하지 않으며, 적용 단계에서 없는 Namespace만 생성해 기존 보안 정책·metadata를 유지합니다.
- `resources`는 상대 경로입니다. checkout이나 overlay를 옮기면 이 경로도 갱신합니다.
- registry 인증이 필요하면 준비한 pull Secret 이름을 DaemonSet의 `spec.template.spec.imagePullSecrets`에 연결하는 패치를 추가합니다. credential 내용은 문서나 Git에 기록하지 않습니다.

#### Control plane을 포함하는 수동 overlay

`FTP_NODES`에 control plane을 포함한다면 위 `kustomization.yaml`의 기존 `patches` 목록에 아래 항목을 추가합니다. 원본에 tolerations가 없는 기준이며, 별도 tolerations가 있으면 기존 항목을 유지하고 두 역할 항목을 추가합니다.

```yaml
- target:
    kind: DaemonSet
    name: ftp
  patch: |-
    - op: add
      path: /spec/template/spec/tolerations
      value:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
        - key: node-role.kubernetes.io/master
          operator: Exists
          effect: NoSchedule
```

### 검사와 렌더 확인

[검사] 관리 호스트의 저장소 루트에서 실행합니다. 다른 계정 파일·env를 쓰면 `ftp-check`에 `FTP_CREDENTIAL_FILE`·`FTP_ENV`를 함께 붙입니다.

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2>
kubectl kustomize "<overlay 디렉터리 절대 경로>"
```

**기대 결과:** 모든 명령이 성공합니다. `ftp-check`는 기존 계정 일치와 전체 대상 노드를 검사하며, 출력하는 `FTP 이미지`는 env 값이므로 overlay 이미지는 렌더 결과로 확인합니다.
렌더 결과의 이미지가 입력한 사내 주소·digest이고 노드 선택 라벨·포트·저장 경로가 원본과 같은지 확인합니다. Namespace와 FTP 계정 Secret은 렌더에 포함되지 않습니다.

### 선택한 노드 전체에 한 번 적용

[변경] 사람이 검증한 overlay 경로를 전달했을 때 관리 호스트의 저장소 루트에서 실행합니다. `FTP_NODES`에는 FTP 대상 노드 전체 목록, `FTP_OVERLAY_DIR`에는 검증한 overlay 경로, `FTP_CREDENTIAL_FILE`에는 사용하는 계정 파일을 넣습니다.

```bash
(
  set -euo pipefail
  FTP_NODES="<노드1,노드2>"
  FTP_OVERLAY_DIR="<검증한 overlay 디렉터리 절대 경로>"
  FTP_CREDENTIAL_FILE="$PWD/deploy/ftp/env/initial-account.env"
  make ftp-check KUBE_CONTEXT="<context>" FTP_NODES="$FTP_NODES" FTP_CREDENTIAL_FILE="$FTP_CREDENTIAL_FILE"
  kubectl kustomize "$FTP_OVERLAY_DIR" >/dev/null

  ftp_namespace="$(kubectl --context "<context>" get namespace etch-ftp --ignore-not-found -o name)"
  if [[ -z "$ftp_namespace" ]]; then
    kubectl --context "<context>" create namespace etch-ftp
  fi
  ftp_secret="$(kubectl --context "<context>" -n etch-ftp get secret ftp-credentials --ignore-not-found -o name)"
  if [[ -z "$ftp_secret" ]]; then
    kubectl --context "<context>" -n etch-ftp create secret generic ftp-credentials \
      --from-env-file="$FTP_CREDENTIAL_FILE"
  fi

  IFS=',' read -r -a ftp_target_nodes <<< "$FTP_NODES"
  kubectl --context "<context>" label node "${ftp_target_nodes[@]}" etch.io/ftp-enabled=true --overwrite
  kubectl --context "<context>" apply -k "$FTP_OVERLAY_DIR"
  kubectl --context "<context>" -n etch-ftp rollout status daemonset/ftp --timeout=300s
  kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide
)
```

**기대 결과:** 각 대상 노드에 Pod가 하나씩 Ready이고 실제 이미지가 사내 주소입니다. 기존 Secret이 계정 파일과 다르면 `ftp-check`에서 중단하며 기존 계정을 덮어쓰지 않습니다.
재배포·노드 추가도 같은 overlay로 [검사와 렌더 확인](#검사와-렌더-확인)과 이 단계를 반복합니다. 사내 이미지 주소·digest는 [저장소 원본](../../shared/docs/infrastructure/repositories.md#서버가-받는-이미지)에 반영합니다.
적용 후 [접속 확인과 운영](02-operations.md)의 1~2단계로 Pod 위치와 업로드·다운로드를 확인합니다.
