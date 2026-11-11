# Worker 추가

[가이드 홈](../README.md#클러스터) · [새 서버 준비](prerequisites.md) · [CP1~3 셋업](control-plane.md) · [Traefik 셋업](../ingress/setup.md)

**목적:** OS만 설치된 새 서버를 기존 kubeadm 클러스터의 Worker로 등록합니다. Airflow용 Worker도 이 문서로 등록합니다.
**준비물:** CP1 관리자 kubeconfig, 새 서버의 SSH/sudo, 사내 미러 접근, 기존 CP1에서 검증된 registry 설정.

확인된 설치 기준은 **Ubuntu 22.04.2 LTS · Kubernetes 1.36.0 · containerd 2.2.1**입니다.
조회 근거와 남은 확인은 [서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)에 있습니다.

## 1. 기존 설치 기준 확인 — CP1

[현재 환경 확인](baseline.md)의 1단계로 `KUBE_CONTEXT`를 설정하고 버전·노드·시스템 Pod를 조회합니다. 설치 도구 후보도 확인합니다.

```bash
command -v kubeadm k3s rke2
```

인프라 담당자의 구축 기록과 기존 Worker에서 OS·Kubernetes·런타임 버전, CRI·cgroup, CNI·MTU·필요한 통신, 패키지·이미지 미러를 확인합니다.
명령이 설치됐다는 사실만으로 구축 도구를 확정하지 않습니다. k3s·RKE2 등으로 관리하는 클러스터는 해당 제품의 Worker 가입 절차를 사용합니다.

## 2. 빈 서버에 프로그램 설치·설정 — 새 Worker

[새 서버 준비](prerequisites.md#1-노드-준비--인프라-담당자각-새-노드)의 노드 준비 항목을 아래 2-1~2-4 명령으로 수행합니다.
**OS만 설치된 새 Ubuntu 22.04 amd64 Worker**에서 순서대로 실행하며 기존 Ready 노드에는 실행하지 않습니다.
kubeadm은 런타임과 kubelet을 자동 설치하지 않습니다.

```bash
cat /etc/os-release
uname -m
hostname
```

**기대 결과:** Ubuntu 22.04, `x86_64`, 고유 hostname이 표시됩니다.

### 2-0. 사용할 사내 미러와 준비 파일

- 패키지와 이미지는 [미러 원본](../infrastructure/repositories.md#패키지chartartifact-주소)의 Nexus 주소에서 받으며, 아래 명령에 그 주소를 직접 표기합니다. 공개 저장소로 직접 접속하지 않습니다.
- Kubernetes 경로는 원본의 `v1.36/deb/` 상대 경로를 미러 base에 이어 붙인 구성입니다. 사내 서버에서의 접속 성공 여부는 별도로 확인합니다.
- 미러 접근이 불가능하면 의존성까지 포함한 승인된 반입 패키지·이미지를 준비합니다.
- Ubuntu 미러는 Ubuntu archive 서명을 보존하는 구성을 기준으로 합니다. 미러가 재서명한다면 담당자가 승인한 키와 `signed-by` 경로를 사용합니다.
- 미러에서 받은 공개 서명키의 지문은 승인된 원본과 대조합니다. 사내 CA·APT 인증이 필요하면 첫 `apt-get update` 전에 호스트 신뢰와 `auth.conf.d`를 준비하며, 인증값을 URL이나 Git에 넣지 않습니다.

**준비 파일:** 기존 CP1에서 검증된 registry별 `hosts.toml`·CA·인증 설정을 안전한 경로로 새 Worker의 `/var/tmp/worker-registry/`에 둡니다.
`registry.k8s.io/hosts.toml`, `docker.io/hosts.toml`처럼 원래 registry 이름별 디렉터리를 사용합니다. 비밀값은 Git에 넣지 않습니다.

설치 명령은 전용 source 파일·빈 추가 source 디렉터리·전용 패키지 색인을 사용합니다.
각 `apt-get`·`apt-cache`에 `APT_MIRROR_OPTIONS`를 전달해 기존 공개 source나 오래된 색인을 사용하지 않으며, 새 터미널에서는 이 배열을 다시 설정합니다.

### 2-1. 기본 설정

다음 명령은 swap을 끄고 재부팅 후 유지될 커널·네트워크 설정을 기록한 뒤 Ubuntu 미러 source를 등록합니다.

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

sudo tee /etc/apt/sources.list.d/worker-mirrors.list >/dev/null <<'EOF'
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://repository.samsungds.net/repository/proxy-apt-archive.ubuntu.com-ubuntu jammy main restricted universe multiverse
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://repository.samsungds.net/repository/proxy-apt-archive.ubuntu.com-ubuntu jammy-updates main restricted universe multiverse
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://repository.samsungds.net/repository/proxy-apt-archive.ubuntu.com-ubuntu jammy-security main restricted universe multiverse
EOF

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y ca-certificates curl gpg
```

### 2-2. containerd 2.2.1 설치

[containerd 공식 안내](https://github.com/containerd/containerd/blob/release/2.2/docs/getting-started.md)의
Docker 배포 패키지를 사내 APT 미러에서 받습니다. `containerd.io`에는 runc도 포함됩니다.
[Ubuntu 저장소 등록 절차](https://docs.docker.com/engine/install/ubuntu/#install-using-the-apt-repository)의
패키지 서명 검증을 유지하며,
패키지 버전은 `2.2.1-1~ubuntu.22.04~jammy`로 고정합니다.

```bash
curl -fsSL http://repository.samsungds.net/repository/proxy-apt-download.docker.com-linux-ubuntu/gpg \
  -o /tmp/worker-docker.asc
gpg --show-keys --with-fingerprint /tmp/worker-docker.asc
```

지문이 승인된 Docker 공개키와 일치하는지 확인한 뒤 저장소를 등록합니다.

```bash
sudo install -m 0644 /tmp/worker-docker.asc /etc/apt/keyrings/worker-docker.asc

echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-docker.asc] http://repository.samsungds.net/repository/proxy-apt-download.docker.com-linux-ubuntu jammy stable' |
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
sudo test -d /var/tmp/worker-registry
sudo cp -a /var/tmp/worker-registry/. /etc/containerd/certs.d/
sudoedit /etc/containerd/config.toml
```

편집기에서 기존 registry 항목의 `config_path`를 다음과 같이 설정합니다. 같은 TOML 테이블을 중복 추가하지 않습니다.

```toml
[plugins.'io.containerd.cri.v1.images'.registry]
  config_path = '/etc/containerd/certs.d'
```

`certs.d`에는 `registry.k8s.io`·`docker.io`와 기존 CNI 등이 사용하는 registry별 설정을 준비합니다.
Kubernetes 이미지용 주소는 `repository.samsungds.net/proxy-docker-registry.k8s.io/<이미지>:<태그>`이며,
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
curl -fsSL http://repository.samsungds.net/repository/proxy-raw-pkgs.k8s.io-core-stable/v1.36/deb/Release.key \
  -o /tmp/worker-kubernetes.key
gpg --show-keys --with-fingerprint /tmp/worker-kubernetes.key
```

지문이 승인된 Kubernetes 공개키와 일치하는지 확인한 뒤 저장소를 등록합니다.

```bash
gpg --batch --yes --dearmor -o /tmp/worker-kubernetes.gpg /tmp/worker-kubernetes.key
sudo install -m 0644 /tmp/worker-kubernetes.gpg /etc/apt/keyrings/worker-kubernetes.gpg

echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-kubernetes.gpg] http://repository.samsungds.net/repository/proxy-apt-pkgs.k8s.io-core-stable/v1.36/deb/ /' |
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
프로젝트의 metrics-server v0.9.0 이미지를 사내 주소로 받아 미러 접근을 확인한 뒤,
같은 이미지의 원래 registry 이름으로도 받아 `hosts.toml` 경로 변환을 검사합니다.

```bash
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock info >/dev/null
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock pull \
  repository.samsungds.net/proxy-docker-registry.k8s.io/metrics-server/metrics-server:v0.9.0
sudo crictl --runtime-endpoint unix:///run/containerd/containerd.sock pull \
  registry.k8s.io/metrics-server/metrics-server:v0.9.0
```

**기대 결과:** 두 `pull`이 성공하고 `apt-cache policy`의 공급 주소가 사내 미러입니다.
kubelet은 join 전에 설정이 없어 재시작을 반복할 수 있습니다. join 이후 상태를 다시 확인합니다.

## 3. Worker 가입 명령 발급 — CP1

kubeadm으로 관리하는 기존 클러스터의 CP1에서 실행합니다.

```bash
sudo kubeadm token create --print-join-command
```

**기대 결과:** **Worker용 가입 명령**이 출력됩니다. 새 Worker로 전달하며 토큰은 Git·공용 로그에 저장하지 않습니다.
endpoint·CA hash를 임의로 바꾸지 않습니다. 기록된 API VIP와 출력된 endpoint가 같은지는 별도로 확인하며, 조회된 CP1 InternalIP로 대체하지 않습니다.

## 4. 클러스터 가입 — 새 Worker

CP1이 출력한 `kubeadm join ...` 전체를 sudo로 실행합니다. Worker용 명령에는 `--control-plane`이 없습니다.
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

**기대 결과:** 예상한 InternalIP·hostname으로 Ready이며, CNI 등 해당 노드의 시스템 Pod가 정상입니다.

**실패 확인:** NotReady이면 새 Worker의 `journalctl -u kubelet -u containerd --since '15 min ago'`와 CNI 상태를 확인합니다.
원인 확인 없이 reset·재가입하지 않습니다.

## 6. 클러스터 인수 확인 — CP1

새 클러스터를 구성했거나 새 Worker를 추가한 뒤 수행합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get --raw='/readyz'
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get service kube-dns
```

담당자가 승인된 진단 이미지와 별도 검증 namespace에서 다음을 확인합니다.

- 각 Worker의 Pod에서 `kubernetes.default.svc` 이름 해석 성공
- 같은 노드·다른 노드의 Pod와 Service 사이 통신 성공
- 사용할 저장소의 PVC 연결·파일 쓰기/읽기 성공
- API LB 상태 검사·backend 전환과 etcd 상태 확인. 운영 노드 중지는 포함하지 않습니다.

**완료 기준:** 새 Worker Ready, 시스템 Pod·클러스터 네트워크 정상, 설치 기준·원본 버전·실행 명령·인수 결과 기록.
Ready만으로 앱 접속까지 검증한 것으로 기록하지 않습니다.

## 다음 단계

- Airflow: [서버 준비](../../../airflow/docs/01-prepare.md#서버-준비)에서 새 Worker의 DB·로그 디렉터리를 준비하고 env의 `NODE_NAME`을 조회한 `kubernetes.io/hostname` 값으로 지정합니다.
- 새 Worker를 외부 HTTPS 진입점으로도 쓸 때: 최초 구성은 [Traefik 셋업](../ingress/setup.md), 운영 중 backend 추가는 [Traefik·VIP 확장](../ingress/expand.md).
- 기존 Traefik은 그대로 사용하며, Worker 추가만으로 앱이나 DB가 자동 이동하지 않습니다.

공식 참고: [Kubernetes 1.36 Linux Worker 추가](https://v1-36.docs.kubernetes.io/docs/tasks/administer-cluster/kubeadm/adding-linux-nodes/).
