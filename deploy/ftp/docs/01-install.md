# FTP 설치

[앱 안내](../README.md) · 다음: [접속 확인과 운영](02-operations.md)

선택한 Linux 노드에 FTP DaemonSet을 한 번 배포합니다. 각 대상 노드에서는 디스크·포트만 확인하고, 검사·배포는 관리 호스트에서 한 번 실행합니다.

- [노드·계정 준비](#노드계정-준비): 1~4단계
- [검사와 배포](#검사와-배포): 5단계 기본 배포
- [별도 overlay 배포](#별도-overlay-배포): 이미지·경로·패치를 직접 관리할 때 5단계 대신 사용
- [완료 확인](#6-완료-확인)

## 노드·계정 준비

### 1. 실행 위치와 준비물

| 위치 | 필요한 작업 |
| --- | --- |
| 관리 호스트(CP1 등) | 저장소 checkout, Python 3.10+·Make·Bash·kubectl, kubeconfig. 검사·배포 실행 |
| FTP를 실행할 각 Linux 노드 | Kubernetes 등록, 저장 디스크·기존 파일 권한·포트 확인 |
| FTP 클라이언트 PC | 대상 노드 IP로 접속할 네트워크·FTP 클라이언트 |

kubectl에는 노드 조회·라벨 변경, namespace·Secret·DaemonSet·ConfigMap 적용과 Pod 조회 권한이 필요합니다.

### 2. 클러스터와 대상 노드 선택

**실행 위치:** 관리 호스트의 저장소 루트. 이후 명령은 같은 Bash 세션에서 실행합니다.

```bash
kubectl config get-contexts
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get nodes -l etch.io/ftp-enabled=true -o wide

read -r -p 'FTP 노드 이름 (여러 개는 쉼표 구분, 공백 없음): ' FTP_NODES
export FTP_NODES
```

`FTP_NODES`에는 노드 목록의 `NAME` 값을 `worker-a` 또는 `worker-a,worker-b`처럼 넣습니다. 노드별로 명령을 반복하지 않습니다.
이미 FTP 라벨이 붙은 노드까지 포함한 **전체 목록**을 입력합니다. 기존 노드를 빼면 검사에서 중단하므로, 노드 제거는 [특정 노드에서 중단](02-operations.md#4-특정-노드에서-중단)을 먼저 수행합니다.
후보 노드의 이름·IP·용도는 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)에서 확인하고 위 조회 결과와 대조합니다. 서버 목록은 FTP 배포 완료 목록이 아닙니다.

검사는 Linux·Ready 상태, cordon·차단 taint, IPv4 InternalIP를 확인합니다.

#### Control plane도 대상에 추가하기

[env/prod.env](../env/prod.env) 또는 사용 중인 `FTP_ENV` 파일의 `FTP_ALLOW_CONTROL_PLANE`이 허용 여부입니다. 기본값과 키를 생략한 값은 `true`이며, 막으려면 `false`로 지정합니다.
`FTP_NODES`에 control plane의 실제 노드 이름을 명시해야 배포 대상이 됩니다.
FTP Pod는 control-plane·master 역할의 `NoSchedule` taint만 허용합니다. 역할 라벨·taint를 제거하지 않으며, 다른 `NoSchedule`·모든 `NoExecute`, cordon·NotReady는 계속 차단합니다.
[별도 overlay 배포](#별도-overlay-배포)에서는 [control plane toleration 패치](#control-plane을-포함하는-수동-overlay)를 함께 추가합니다.

**기대 결과:** `KUBE_CONTEXT`, `FTP_NODES`가 export되어 있습니다.

### 3. 각 노드의 저장 폴더와 포트 확인

**실행 위치:** 선택한 **각 노드**에 SSH로 접속해 실행합니다. control plane을 포함했다면 해당 노드도 확인합니다.

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

**실행 위치:** 관리 호스트의 저장소 루트, 2단계와 같은 Bash 세션.

[credentials.env.example](../credentials.env.example)을 **Git 밖**의 파일로 복사해 실제 계정을 입력합니다. 이미 사용 중인 계정 파일이 있으면 그 절대 경로를 입력하며 파일을 다시 만들지 않습니다.

```bash
read -r -p 'FTP 계정 파일 절대 경로 (Git 밖): ' FTP_CREDENTIAL_FILE
export FTP_CREDENTIAL_FILE
(
  set -euo pipefail
  [[ "$FTP_CREDENTIAL_FILE" = /* ]]
  umask 077
  if [[ ! -e "$FTP_CREDENTIAL_FILE" ]]; then
    cp deploy/ftp/credentials.env.example "$FTP_CREDENTIAL_FILE"
  fi
)
chmod 600 "$FTP_CREDENTIAL_FILE"
vi "$FTP_CREDENTIAL_FILE"
```

- `FTP_USER=값`, `FTP_PASS=값` 두 줄을 입력합니다. `export`나 값을 감싸는 따옴표는 넣지 않습니다.
- 사용자 이름에는 영문·숫자·밑줄·하이픈만 사용합니다. 비밀번호는 비워 두지 않으며 줄바꿈·역슬래시를 넣지 않습니다.
- 모든 대상 노드는 `etch-ftp/ftp-credentials` Secret을 공유합니다. 기본 계정은 없습니다.
- 새 Bash 세션에서는 같은 경로를 `FTP_CREDENTIAL_FILE`로 다시 export합니다.

**완료 기준:** `KUBE_CONTEXT`, `FTP_NODES`, `FTP_CREDENTIAL_FILE`이 export되어 있고 각 노드의 디스크·포트·방화벽 요청을 확인했습니다. 기본 배포는 [5단계](#5-검사-후-배포), 별도 overlay 운영은 [별도 overlay 배포](#별도-overlay-배포)로 진행합니다.

## 검사와 배포

### 5. 검사 후 배포

**실행 위치:** 관리 호스트의 저장소 루트, 1~4단계의 세 변수를 export한 Bash 세션.

**입력:** 실행기는 [env/prod.env](../env/prod.env)를 읽어 `FTP_IMAGE`(사내 Docker Hub 미러, 원본 digest 고정), `IMAGE_PULL_SECRET`, `FTP_ALLOW_CONTROL_PLANE`을 적용합니다.

- 다른 경로·digest가 필요하면 env의 `FTP_IMAGE`를 실제 주소로 바꿉니다. `http://`, `https://`는 붙이지 않습니다. 사내 미러의 해당 digest 제공 여부·접근·CA는 Worker에서 확인합니다.
- registry 인증이 필요하면 `etch-ftp` namespace에 pull Secret을 미리 만들고 `IMAGE_PULL_SECRET`에 이름을 입력합니다. 빈 값이면 추가하지 않습니다.
- 별도 env는 `export FTP_ENV=/절대/경로/ftp.env`로 지정합니다. 이미지 설정 env와 FTP 로그인 계정 파일은 별개입니다.

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check

# 위 검사가 통과하고 출력된 context·노드·IP가 맞으면 실행합니다.
make ftp-up
```

| 명령 | 영향 | 처리 내용 |
| --- | --- | --- |
| `server-check` | 조회 없음 | `k8s/start.sh` 문법과 Kustomize 원본 렌더 |
| `ftp-check` | 클러스터 조회만 | 이미지 설정·선택 pull Secret 존재, 계정 형식·권한, 원본 렌더, 대상 노드 상태, 기존 Secret 일치 여부 |
| `ftp-up` | 적용 | 같은 검사 → 없는 namespace 생성 → 없는 Secret 생성 → 노드 라벨 → 스택 적용 → 최대 5분 기동 대기 → Pod 위치 출력 |

**기대 결과:** `ftp-up`이 대상 노드별 Pod 위치를 출력하고 `FTP 배포 완료`로 끝납니다.

**실패 확인:**

- 기존 Secret이 계정 파일과 다르면 변경 전에 중단합니다. 기존 계정 파일을 사용하거나 [계정 변경](02-operations.md#5-계정-변경)을 따릅니다.
- 배포 중 실패하면 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 재실행합니다. 재실행은 파일 데이터를 삭제하지 않습니다.
- 검사 통과는 이미지 pull·원격 디스크·방화벽·실제 FTP 인증 성공을 보장하지 않습니다. [문제 해결](02-operations.md#6-문제-해결)을 확인합니다.

`kubectl apply -k deploy/ftp/k8s`를 직접 실행하면 env가 적용되지 않아 공개 이미지를 사용하고 control plane toleration도 추가되지 않습니다. 직접 적용이 필요하면 아래 별도 overlay 배포를 사용합니다.

**다음 단계:** [6. 완료 확인](#6-완료-확인)

## 별도 overlay 배포

이미지·저장 경로·추가 패치를 Git 밖 overlay로 관리할 때 [5단계](#5-검사-후-배포) 대신 사용합니다. 두 배포 방식을 함께 실행하지 않으며, overlay 운영 중에는 `make ftp-up`을 사용하지 않습니다.
env와 overlay는 자동으로 합쳐지지 않습니다. overlay의 이미지·pull Secret·toleration은 아래 입력으로 직접 지정합니다.

**준비물:** 1~4단계 완료, 승인된 사내 registry에서 **실제로 확인한** `fauria/vsftpd` 이미지 경로와 digest. 원본 digest를 그대로 쓰려면 사내 registry에서도 같은 digest로 조회되는지 확인합니다.

기본 경로가 다른 서버는 같은 목적의 경로를 준비하거나, 별도 overlay에서 hostPath와 노드 선택 라벨·DaemonSet 이름을 함께 변경해 서로 겹치지 않는 노드 그룹으로 배포합니다.

### 5-1. Git 밖에 overlay 작성

**실행 위치:** 관리 호스트의 저장소 루트, 1~4단계와 같은 Bash 세션.
**입력:** `FTP_IMAGE_REPOSITORY`는 태그·digest 없는 registry/이미지 경로, `FTP_IMAGE_DIGEST`는 `sha256:...`, `FTP_OVERLAY_DIR`는 Git 밖의 **새 디렉터리 절대 경로**입니다. 기존 overlay가 있으면 이 단계를 반복하지 않고 저장된 경로를 export합니다.

```bash
read -r -p '사내 FTP 이미지 경로 (태그·digest 제외): ' FTP_IMAGE_REPOSITORY
read -r -p '사내에서 확인한 이미지 digest (sha256:...): ' FTP_IMAGE_DIGEST
read -r -p '새 FTP overlay 디렉터리 절대 경로: ' FTP_OVERLAY_DIR
export FTP_OVERLAY_DIR
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

### 5-2. 검사와 렌더 확인

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check
kubectl kustomize "$FTP_OVERLAY_DIR"
```

**기대 결과:** 모든 명령이 성공합니다. `ftp-check`는 기존 계정 일치와 전체 대상 노드를 검사하며, 출력하는 `FTP 이미지`는 env 값이므로 overlay 이미지는 렌더 결과로 확인합니다.
렌더 결과의 이미지가 입력한 사내 주소·digest이고 노드 선택 라벨·포트·저장 경로가 원본과 같은지 확인합니다. Namespace와 FTP 계정 Secret은 렌더에 포함되지 않습니다.

### 5-3. 선택한 노드 전체에 한 번 적용

```bash
(
  set -euo pipefail
  : "${KUBE_CONTEXT:?context를 지정하세요.}"
  : "${FTP_NODES:?FTP 대상 노드 전체 목록을 지정하세요.}"
  : "${FTP_CREDENTIAL_FILE:?계정 파일을 지정하세요.}"
  : "${FTP_OVERLAY_DIR:?검증한 overlay 경로를 지정하세요.}"
  make ftp-check
  kubectl kustomize "$FTP_OVERLAY_DIR" >/dev/null

  ftp_namespace="$(kubectl --context "$KUBE_CONTEXT" get namespace etch-ftp --ignore-not-found -o name)"
  if [[ -z "$ftp_namespace" ]]; then
    kubectl --context "$KUBE_CONTEXT" create namespace etch-ftp
  fi
  ftp_secret="$(kubectl --context "$KUBE_CONTEXT" -n etch-ftp get secret ftp-credentials --ignore-not-found -o name)"
  if [[ -z "$ftp_secret" ]]; then
    kubectl --context "$KUBE_CONTEXT" -n etch-ftp create secret generic ftp-credentials \
      --from-env-file="$FTP_CREDENTIAL_FILE"
  fi

  IFS=',' read -r -a ftp_target_nodes <<< "$FTP_NODES"
  kubectl --context "$KUBE_CONTEXT" label node "${ftp_target_nodes[@]}" etch.io/ftp-enabled=true --overwrite
  kubectl --context "$KUBE_CONTEXT" apply -k "$FTP_OVERLAY_DIR"
  kubectl --context "$KUBE_CONTEXT" -n etch-ftp rollout status daemonset/ftp --timeout=300s
  kubectl --context "$KUBE_CONTEXT" -n etch-ftp get pods -l app=ftp -o wide
)
```

**기대 결과:** 각 대상 노드에 Pod가 하나씩 Ready이고 실제 이미지가 사내 주소입니다. 기존 Secret이 계정 파일과 다르면 `ftp-check`에서 중단하며 기존 계정을 덮어쓰지 않습니다.
재배포·노드 추가도 같은 overlay로 5-2~5-3을 반복합니다. 사내 이미지 주소·digest는 [저장소 원본](../../shared/docs/infrastructure/repositories.md#서버가-받는-이미지)에 반영합니다.

## 6. 완료 확인

[접속 확인과 운영](02-operations.md)의 1~2단계로 각 노드의 Pod `NODE`, 실제 접속 IP, 업로드·다운로드와 호스트 파일 위치를 확인하면 설치가 완료됩니다.
다른 노드의 저장 폴더에 테스트 파일이 생기지 않는 것도 확인합니다. Pod Ready·렌더 검사만으로 실제 전송 성공을 대신하지 않습니다.
현재 구성은 IPv4 직접 접속과 passive 모드용이며 TLS나 NAT 주소를 자동 설정하지 않습니다.

검증 후 [FTP 서비스 기록](../../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 대상 노드·접속 주소·검증 결과를, [FTP 네트워크 기록](../../shared/docs/infrastructure/network.md#ftp-직접-접속)에 실제 방화벽 확인 결과를 갱신합니다.
