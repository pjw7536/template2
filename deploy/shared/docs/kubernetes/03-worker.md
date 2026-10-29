# 03. Worker 추가

[가이드 홈](README.md) · [CP1~3 셋업](01-control-plane.md) · [Traefik 셋업](02-traefik.md)

목표는 **OS만 설치된 새 서버를 기존 클러스터의 Worker로 등록하는 것**입니다.
기존 클러스터의 설치 방식과 버전을 먼저 확인합니다. 아래 가입 명령은 kubeadm 방식에 해당합니다.
Airflow용 Worker를 추가할 때도 이 문서만 따라 등록한 뒤 Airflow 배포 문서로 이동합니다.

확인된 설치 기준은 **Ubuntu 22.04.2 LTS · Kubernetes 1.36.0 · containerd 2.2.1**입니다.
조회 근거와 아직 확인할 항목은 [서버 현황](../infrastructure/cluster.md#확인된-worker-설치-기준)에 있습니다.

## 1. 기존 설치 기준 확인 — CP1

```bash
kubectl config get-contexts
read -r -p '기존 서버 context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" version -o yaml
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
command -v kubeadm k3s rke2
```

인프라 담당자의 구축 기록과 기존 Worker에서 OS·Kubernetes·런타임 버전, CRI·cgroup,
CNI·MTU·필요한 통신, 패키지·이미지 미러를 확인합니다.
명령이 설치됐다는 사실만으로 구축 도구를 확정하지 않습니다.
k3s·RKE2 등으로 관리하는 클러스터는 해당 제품의 Worker 가입 절차를 사용합니다.

## 2. 빈 서버에 프로그램 설치·설정 — 새 Worker

새 서버에서 OS·CPU를 확인합니다.

```bash
cat /etc/os-release
uname -m
hostname
```

| 순서 | 할 일 | 완료 기준 |
| --- | --- | --- |
| 1 | 고유 hostname·고정 IP·DNS·시간 동기화·디스크 준비 | 재부팅 후에도 주소·디스크 마운트 유지 |
| 2 | OS·버전에 맞는 swap·커널·네트워크 설정 | 기존 CNI에 필요한 노드 간 통신 가능 |
| 3 | containerd 등 기존 운영 방식과 호환되는 런타임 설치 | CRI 활성화·kubelet과 cgroup 설정 일치 |
| 4 | 기존 클러스터에 맞는 kubelet·kubeadm 설치 | 선택한 패키지 버전 확인 |
| 5 | registry의 CA·인증·mirror 설정 | 새 노드 런타임에서 필요한 이미지 접근 가능 |

kubeadm은 런타임과 kubelet을 자동 설치하지 않습니다. 아래 2-1~2-4는
**OS만 설치된 새 Ubuntu 22.04 amd64 Worker**에서 순서대로 실행합니다.
`uname -m`이 `x86_64`인지 확인하며, 기존 Ready 노드에는 실행하지 않습니다.

**사내 미러 사용:** Ubuntu·Docker·Kubernetes 패키지와 실행 이미지는 사내 미러에서 받습니다.
아래 입력을 먼저 준비하며, 설치 명령에서 공개 저장소로 직접 접속하지 않습니다.
미러 접근이 불가능하면 의존성까지 포함한 승인된 반입 패키지·이미지를 준비합니다.

### 2-0. 사내 미러 입력 준비

운영 환경의 실제 URL을 환경변수로 전달합니다. 아래 미러 이름은 저장소의 미러 참고표 기준이며,
접속 scheme·호스트·인증·버전별 하위 경로는 운영 담당자에게 확인합니다.
특히 Kubernetes URL은 **v1.36의 `deb` 저장소를 제공하는 최종 주소**를 입력하며 경로를 추측하지 않습니다.

| 환경변수 | 입력값 | 사내 미러 이름 |
| --- | --- | --- |
| `UBUNTU_APT_MIRROR_URL` | Jammy·updates·security를 제공하는 Ubuntu APT base URL | `proxy-apt-archive.ubuntu.com-ubuntu` |
| `DOCKER_APT_MIRROR_URL` | Ubuntu용 Docker APT base URL | `proxy-apt-download.docker.com-linux-ubuntu` |
| `KUBERNETES_APT_MIRROR_URL` | Kubernetes v1.36 `deb` 저장소 URL | `proxy-apt-pkgs.k8s.io-core-stable` |
| `DOCKER_APT_KEY_FILE` | 승인된 Docker 공개 서명키 파일 절대 경로, `.asc` 형식 | 별도 반입 |
| `KUBERNETES_APT_KEYRING_FILE` | 승인된 Kubernetes 공개 서명키 파일 절대 경로, dearmor한 `.gpg` 형식 | 별도 반입 |
| `CONTAINERD_REGISTRY_CONFIG_DIR` | 기존 CP1 기준으로 검증한 registry별 `hosts.toml`·CA를 담은 디렉터리 | 별도 전달 |

Ubuntu 미러는 기존 Ubuntu archive 서명을 보존하는 구성을 기준으로 합니다.
미러가 패키지를 재서명한다면 담당자가 승인한 키와 `signed-by` 경로를 사용합니다.
서명키의 지문·반입 파일 체크섬을 승인된 원본과 대조하고,
사내 CA·APT 인증이 필요하면 첫 `apt-get update` 전에 호스트 신뢰와 `auth.conf.d`를 준비합니다.
인증값을 미러 URL에 넣거나 Git에 기록하지 않습니다.

같은 Bash 터미널에서 승인된 값으로 환경변수를 설정한 뒤 아래 검사를 실행합니다.
패키지 서명키·CA·registry 설정 파일을 받기 위해 공개 URL로 접속하지 않습니다.

```bash
: "${UBUNTU_APT_MIRROR_URL:?Ubuntu 사내 APT base URL을 설정하세요}"
: "${DOCKER_APT_MIRROR_URL:?Docker 사내 APT base URL을 설정하세요}"
: "${KUBERNETES_APT_MIRROR_URL:?Kubernetes v1.36 사내 APT URL을 설정하세요}"
: "${DOCKER_APT_KEY_FILE:?승인된 Docker 공개 서명키 파일을 지정하세요}"
: "${KUBERNETES_APT_KEYRING_FILE:?승인된 Kubernetes 공개 keyring 파일을 지정하세요}"
: "${CONTAINERD_REGISTRY_CONFIG_DIR:?승인된 registry 설정 디렉터리를 지정하세요}"

sudo test -r "$DOCKER_APT_KEY_FILE"
sudo test -r "$KUBERNETES_APT_KEYRING_FILE"
sudo test -d "$CONTAINERD_REGISTRY_CONFIG_DIR"
```

아래 설치 명령은 전용 source 파일·빈 추가 source 디렉터리·전용 패키지 색인을 사용합니다.
각 `apt-get`·`apt-cache`에 `APT_MIRROR_OPTIONS`를 전달해 기존 공개 source나 오래된 색인을 사용하지 않습니다.
새 터미널에서는 환경변수와 이 배열을 다시 설정합니다.

### 2-1. 기본 설정

고유 hostname·고정 IP·DNS·시간 동기화와 기존 API endpoint·CNI 통신을 먼저 준비합니다.
다음 명령은 swap을 끄고 재부팅 후 유지될 커널·네트워크 설정을 기록합니다.

```bash
sudo swapoff -a
sudo sed -i.bak '/^[[:space:]]*#/! { /[[:space:]]swap[[:space:]]/ s/^/#/; }' /etc/fstab

printf 'overlay\nbr_netfilter\n' | sudo tee /etc/modules-load.d/kubernetes.conf
sudo modprobe overlay
sudo modprobe br_netfilter

printf 'net.ipv4.ip_forward=1\nnet.bridge.bridge-nf-call-iptables=1\nnet.bridge.bridge-nf-call-ip6tables=1\n' |
  sudo tee /etc/sysctl.d/99-kubernetes.conf
sudo sysctl --system

sudo install -d -m 0755 /etc/apt/keyrings
sudo install -d -m 0755 /etc/apt/worker-empty-sources

APT_MIRROR_OPTIONS=(
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/worker-mirrors.list
  -o Dir::Etc::sourceparts=/etc/apt/worker-empty-sources
  -o Dir::State::lists=/var/lib/apt/lists-worker-mirrors
  -o APT::Update::Error-Mode=any
)

printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] %s %s main restricted universe multiverse\n' \
  "${UBUNTU_APT_MIRROR_URL%/}" jammy \
  "${UBUNTU_APT_MIRROR_URL%/}" jammy-updates \
  "${UBUNTU_APT_MIRROR_URL%/}" jammy-security |
  sudo tee /etc/apt/sources.list.d/worker-mirrors.list

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y ca-certificates
```

### 2-2. containerd 2.2.1 설치

[containerd 공식 안내](https://github.com/containerd/containerd/blob/release/2.2/docs/getting-started.md)의
Docker 배포 패키지를 사내 APT 미러에서 받습니다. `containerd.io`에는 runc도 포함됩니다.
[Ubuntu 저장소 등록 절차](https://docs.docker.com/engine/install/ubuntu/#install-using-the-apt-repository)의
패키지 서명 검증을 유지하며,
패키지 버전은 `2.2.1-1~ubuntu.22.04~jammy`로 고정합니다.

```bash
sudo install -m 0644 "$DOCKER_APT_KEY_FILE" /etc/apt/keyrings/worker-docker.asc

printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-docker.asc] %s jammy stable\n' \
  "${DOCKER_APT_MIRROR_URL%/}" |
  sudo tee -a /etc/apt/sources.list.d/worker-mirrors.list

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y containerd.io=2.2.1-1~ubuntu.22.04~jammy
sudo apt-mark hold containerd.io
```

### 2-3. containerd CRI·cgroup 설정

아래는 새 런타임의 초기 설정입니다. 이미 구성된 containerd가 있다면 기존 registry·CA·인증 설정을
덮어쓰지 말고 필요한 항목만 병합합니다.
[containerd 2.x 설정 기준](https://v1-36.docs.kubernetes.io/docs/setup/production-environment/container-runtimes/#configuring-the-systemd-cgroup-driver)에
맞춰 CRI가 활성화된 기본 설정과 `SystemdCgroup = true`를 사용합니다.

```bash
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

sudo install -d -m 0755 /etc/containerd/certs.d
sudo cp -a "$CONTAINERD_REGISTRY_CONFIG_DIR/." /etc/containerd/certs.d/
sudoedit /etc/containerd/config.toml
```

편집기에서 기존 registry 항목의 `config_path`를 다음과 같이 설정합니다. 같은 TOML 테이블을 중복 추가하지 않습니다.

```toml
[plugins.'io.containerd.cri.v1.images'.registry]
  config_path = '/etc/containerd/certs.d'
```

`certs.d`에는 `registry.k8s.io`·`docker.io`와 기존 CNI 등이 사용하는 registry별 설정을 준비합니다.
Kubernetes 이미지용 미러 이름은 `proxy-docker-registry.k8s.io`이며,
실제 이미지 경로 변환과 인증은 기존 CP1에서 검증된 구성을 따릅니다.
[containerd registry 설정](https://github.com/containerd/containerd/blob/release/2.2/docs/hosts.md)에 따라
각 `hosts.toml`의 `server`도 사내 미러를 가리키게 해 공개 registry fallback을 방지합니다.
`pull`·`resolve` 권한, `/v2`·미러 prefix 경로, CA·인증을 확인합니다.
공개 registry를 `server`에 남기거나 TLS 검증을 끄지 않습니다.

```bash
sudo systemctl enable --now containerd
sudo systemctl restart containerd
```

### 2-4. kubeadm·kubelet 1.36.0 설치

[Kubernetes 1.36 공식 설치 절차](https://v1-36.docs.kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)를
사용하되 kubeadm·kubelet 패키지를 `1.36.0-1.1`로 고정합니다.
kubelet 의존성으로 기본 CNI 실행 파일도 설치됩니다. 클러스터 CNI 구성은 기존 운영 설정을 유지합니다.

```bash
sudo install -m 0644 "$KUBERNETES_APT_KEYRING_FILE" /etc/apt/keyrings/worker-kubernetes.gpg

printf 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-kubernetes.gpg] %s /\n' \
  "${KUBERNETES_APT_MIRROR_URL%/}" |
  sudo tee -a /etc/apt/sources.list.d/worker-mirrors.list

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y kubeadm=1.36.0-1.1 kubelet=1.36.0-1.1
sudo apt-mark hold kubeadm kubelet
sudo systemctl enable --now kubelet
```

설치 후 새 Worker에서 확인합니다.

```bash
kubeadm version -o short
kubelet --version
containerd --version
systemctl is-active containerd
dpkg-query -W -f='${Package}\t${Version}\n' kubeadm kubelet containerd.io
apt-cache "${APT_MIRROR_OPTIONS[@]}" policy containerd.io kubeadm kubelet
```

`apt-cache policy`의 공급 주소가 사내 미러인지 확인합니다. 의존 패키지인 `cri-tools`·`kubernetes-cni`도
미러에 있어야 하며, 버전이나 패키지가 없으면 미러 동기화·반입을 요청합니다.
승인된 이미지 한 개로 다음 CRI 조회·pull을 확인한 뒤 가입합니다.
이미지 이름은 운영 환경에서 사용하는 원래 registry 이름을 포함해 `hosts.toml` 경로 변환까지 검사합니다.

```bash
read -r -p '미러로 받을 승인된 검사 이미지 이름과 tag: ' WORKER_CHECK_IMAGE
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock info >/dev/null
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock pull "$WORKER_CHECK_IMAGE"
```

kubelet은 join 전에 설정이 없어 재시작을 반복할 수 있습니다. join 이후 상태를 다시 확인합니다.
기록된 API VIP와 실제 가입 endpoint가 같은지는 별도로 확인합니다.
가입에는 다음 단계에서 CP1이 출력한 endpoint를 사용하며, 조회된 CP1 InternalIP로 임의 대체하지 않습니다.

## 3. Worker 가입 명령 발급 — CP1

kubeadm으로 관리하는 기존 클러스터의 CP1에서 실행합니다.

```bash
sudo kubeadm token create --print-join-command
```

출력된 **Worker용 가입 명령**을 새 Worker로 전달합니다.
토큰은 Git·공용 로그에 저장하지 않습니다. endpoint·CA hash를 임의로 바꾸지 않습니다.

## 4. 클러스터 가입 — 새 Worker

CP1이 출력한 `kubeadm join ...` 전체를 sudo로 실행합니다.
Worker용 명령에는 `--control-plane`이 없습니다.
기존 Ready 노드에 다시 join하지 않으며 새 Worker에서 `kubeadm init`을 실행하지 않습니다.

## 5. 등록·네트워크 확인 — CP1

```bash
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
read -r -p '새 Worker의 노드 이름: ' NEW_WORKER
kubectl --context "$KUBE_CONTEXT" wait --for=condition=Ready "node/$NEW_WORKER" --timeout=300s
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide \
  --field-selector "spec.nodeName=$NEW_WORKER"
```

예상한 InternalIP·hostname인지, CNI 등 해당 노드의 시스템 Pod가 정상인지 확인합니다.
승인된 진단 이미지로 새 노드의 Pod DNS·기존 노드/Service 통신도 확인합니다.
NotReady이면 새 Worker의 `journalctl -u kubelet -u containerd --since '15 min ago'`와
CNI 상태를 확인합니다. 원인 확인 없이 reset·재가입하지 않습니다.

**완료:** 새 Worker Ready + 시스템 Pod·클러스터 네트워크 정상.

Airflow를 설치하려면 [서버 준비](../../../airflow/01_SERVER_SETUP.md)에서 새 Worker의
DB·로그 디렉터리를 준비하고 env의 `NODE_NAME`을 조회한 `kubernetes.io/hostname` 값으로 지정합니다.
기존 Traefik은 그대로 사용하며 Worker 추가만으로 앱이나 DB가 자동 이동하지 않습니다.

새 Worker를 외부 HTTPS 진입점으로도 쓸 때만 [02. Traefik 셋업](02-traefik.md)을 추가로 진행합니다.
백업·복구를 포함한 기존 ingress 확장 절차는 [Traefik·VIP 확장](../../ingress/02-ADD_WORKER.md)에 있습니다.

공식 참고: [Kubernetes 1.36 Linux Worker 추가](https://v1-36.docs.kubernetes.io/docs/tasks/administer-cluster/kubeadm/adding-linux-nodes/).
