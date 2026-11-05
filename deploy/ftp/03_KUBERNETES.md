# 03. FTP Kubernetes 원본과 수동 배포

[시작 안내](README.md) · [자동 배포](01_SERVER_SETUP.md)

기본 이미지를 사용하는 설치는 `make ftp-check` → `make ftp-up` 순서로 진행합니다.
사내 Worker별 배포는 아래의 [사내 이미지 적용](#사내-이미지로-각-worker에-배포)을 따릅니다. 두 배포 방식을 중복 실행하지 않습니다.

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

FTP가 필요한 Linux Worker에 `etch.io/ftp-enabled=true` 라벨을 붙이면 DaemonSet이
노드마다 Pod 하나를 실행합니다. `hostNetwork`로 해당 노드 IP에 직접 접속하며
Service·Ingress·VIP를 사용하지 않습니다. Kubernetes에 등록되지 않은 서버에는 배치되지 않습니다.

| 항목 | 설정 |
| --- | --- |
| 접속 주소 | 대상 노드 InternalIP, TCP 6380 |
| Passive 주소 | Downward API의 `status.hostIP` |
| Passive 포트 | TCP 8076–8079 |
| 노드 저장 폴더 | `/appdata/data_movement` |
| 컨테이너 저장 폴더 | `/data/data_movement` |
| 로그인 후 업로드 경로 | `data_movement/` |
| 계정 | `etch-ftp` namespace의 `ftp-credentials` Secret |

노드별 파일은 독립적이며 자동 복제·이동하지 않습니다. 소비 앱이 다른 노드에 있으면
별도 공유 저장소 또는 파일 전송이 필요합니다.

기존 Compose의 `ftp` DNS 이름은 생성하지 않습니다. 기존 클라이언트의 접속 설정을 대상 노드 IP와 6380으로 변경합니다.
외부 PC 개발에는 `local/ftp/k8s`의 Kubernetes overlay를 사용합니다. FTP 전용 Compose는 제거됐습니다.

## 준비

1. 선택 체크아웃이면 `bash deploy/shared/scripts/checkout-server.sh ftp`를 실행합니다.
2. 각 대상 Worker에서 저장 디스크·기존 데이터·권한을 확인합니다.
   `/appdata/data_movement`가 없으면 `DirectoryOrCreate` 설정으로 kubelet이 Pod 시작 전에 생성합니다. 수동 생성은 필수가 아닙니다.
   기존 데이터를 이관할 때는 해당 경로로 옮깁니다. 시작 스크립트는 최상위 폴더 소유자를 이미지의 `ftp` 사용자로 변경합니다.
   하위 파일의 소유권은 변경하지 않으므로 기존 데이터의 읽기·쓰기 권한을 별도로 맞춥니다.
3. 기존 FTP가 해당 포트를 점유하고 있으면 중단합니다. 클라이언트에서 노드 InternalIP의
   TCP 6380과 8076–8079에 접근할 수 있도록 방화벽을 설정합니다.
   이 구성은 IPv4 직접 접속·passive 모드 기준이며 NAT 주소나 TLS를 자동 설정하지 않습니다.
4. 기본 이미지는 기존 FTP와 같은 `fauria/vsftpd`이며 접속 검증한 digest로 고정합니다. 사내 반입 시 외부 overlay의
   Kustomize `images`로 승인된 registry 주소와 검증한 digest를 지정합니다.
   실제 배포도 동일한 overlay를 사용하고 필요한 imagePullSecrets를 추가합니다.

기본 경로가 다른 서버는 같은 목적의 경로를 준비하거나, 별도 overlay에서 hostPath와
노드 선택 라벨·DaemonSet 이름을 함께 변경해 서로 겹치지 않는 노드 그룹으로 배포합니다.
hostNetwork와 hostPath를 허용하는 namespace 정책이 필요합니다.

## 사내 이미지로 각 Worker에 배포

### 1. 실행 위치와 입력

이후 명령은 **CP1 또는 관리 호스트의 저장소 루트, 동일한 Bash 세션**에서 실행합니다.
[서버 설치 1~4절](01_SERVER_SETUP.md)을 먼저 마쳐 `KUBE_CONTEXT`, `FTP_NODES`, `FTP_CREDENTIAL_FILE`을 export합니다.
계정 파일은 [계정 파일 준비](01_SERVER_SETUP.md#4-관리-호스트의-계정-파일-준비)에 따라 서버에서
[credentials.env.example](credentials.env.example)을 수정하거나 기존 파일을 사용합니다.
`FTP_CREDENTIAL_FILE`에는 실제 값이 입력되고 권한 `600`이 적용된 파일의 절대 경로를 지정합니다.
각 Worker의 저장 디스크·기존 파일 권한·포트 확인도 끝나 있어야 합니다. 없는 데이터 폴더는 Pod 시작 전에 생성됩니다.
기본 계정은 없고 모든 대상 노드는 같은 Secret을 사용합니다.

승인된 사내 registry에 `fauria/vsftpd` 이미지를 반입하거나 미러로 제공하고 **실제로 확인한 경로와 digest**를 준비합니다.
원본의 digest를 그대로 쓰려면 같은 이미지가 사내 registry에서도 그 digest로 조회되는지 확인해야 합니다.
사내 최종 FTP 이미지 주소는 아직 기록돼 있지 않으므로 아래 입력으로 지정합니다.

### 2. Git 밖에 overlay 작성

`FTP_IMAGE_REPOSITORY`에는 태그·digest 없는 registry/이미지 경로, `FTP_IMAGE_DIGEST`에는 `sha256:...`를 입력합니다.
`FTP_OVERLAY_DIR`는 Git 밖의 **새 디렉터리 절대 경로**입니다. 기존 overlay가 있으면 이 생성 단계를 반복하지 않고 저장된 경로를 사용합니다.

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

이 overlay의 Namespace 제외 패치는 렌더 결과에서만 Namespace를 뺍니다. 클러스터의 Namespace를 삭제하지 않습니다.
아래 배포 단계에서 없는 Namespace만 생성해 기존 보안 정책·metadata를 유지합니다.
Kustomize의 디렉터리 참조는 상대 경로로 생성합니다. 관리 호스트의 checkout이나 overlay를 옮기면 `resources` 경로도 갱신합니다.

registry 인증이 필요하면 `etch-ftp` namespace에 준비한 pull Secret 이름을 DaemonSet의
`spec.template.spec.imagePullSecrets`에 연결하는 overlay 패치를 추가합니다.
노드의 registry CA·접근 권한도 준비합니다. credential 내용은 문서나 Git에 기록하지 않습니다.

### 3. 검사와 렌더 확인

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check
kubectl kustomize "$FTP_OVERLAY_DIR"
```

모든 명령이 성공한 뒤 진행합니다. `ftp-check`는 기존 계정 일치와 **전체 대상 Worker**를 검사합니다.
렌더 결과에서 이미지가 입력한 사내 주소·digest인지, 노드 선택 라벨·포트·저장 경로가 원본 계약과 같은지 확인합니다.
Namespace와 FTP 계정 Secret은 이 렌더에 포함되지 않습니다.

### 4. 선택한 Worker 전체에 한 번 적용

```bash
(
  set -euo pipefail
  : "${KUBE_CONTEXT:?context를 지정하세요.}"
  : "${FTP_NODES:?대상 Worker 전체 목록을 지정하세요.}"
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

기존 Secret이 계정 파일과 다르면 `ftp-check`에서 중단합니다. 이 절차는 기존 계정을 덮어쓰지 않습니다.
배포 후에는 각 대상 Worker에 Pod가 하나씩 있고 실제 이미지가 사내 주소인지 확인합니다.
재배포할 때도 이 적용 블록과 같은 overlay를 사용합니다. `make ftp-up`은 기본 원본을 다시 적용하므로 사내 overlay 운영 중에는 사용하지 않습니다.

### 5. 노드별 파일 전송과 추가 노드

[접속 확인과 운영](02_OPERATIONS.md#2-업로드다운로드-확인)에 따라 각 Worker IP의 6380으로 로그인하고
Passive 모드로 `data_movement/`에 서로 다른 이름의 파일을 올려 다운로드합니다.
접속한 Worker의 `/appdata/data_movement`에만 해당 파일이 생겼는지 확인합니다.
Pod Ready·렌더 검사만으로 실제 전송 성공을 대신하지 않습니다.

새 Worker를 추가할 때는 해당 서버의 디스크·기존 파일 권한·방화벽을 먼저 확인합니다. 없는 데이터 폴더는 자동 생성됩니다.
`FTP_NODES`에 기존 대상과 새 노드를 모두 넣고 이 문서의 검사·적용 절차를 반복합니다.
사내 이미지 주소·digest·배포 결과는 [저장소 원본](../shared/docs/infrastructure/repositories.md)과
[FTP 서비스 원본](../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 확인일·근거와 함께 반영합니다.

## 중단

특정 노드에서만 중단하려면 라벨을 제거합니다. 데이터 폴더와 파일은 남습니다.

```bash
read -r -p 'FTP를 중단할 Worker 이름: ' FTP_STOP_NODE
kubectl --context "$KUBE_CONTEXT" label node "$FTP_STOP_NODE" etch.io/ftp-enabled-
```

## 원본

- `k8s/stack.yaml`: namespace·DaemonSet·Secret 참조·노드 폴더 마운트
- `k8s/start.sh`: 기존 포트와 저장 경로 적용, 기본 계정 실행 방지
- `k8s/kustomization.yaml`: 스크립트 변경 시 Pod가 갱신되는 ConfigMap 생성

설계 근거: [Kubernetes DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/),
[vsftpd 이미지 시작 스크립트](https://github.com/fauria/docker-vsftpd/blob/master/run-vsftpd.sh).
