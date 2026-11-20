# Worker 추가

[가이드 홈](../README.md#클러스터) · [새 서버 준비](prerequisites.md) · [CP1~3 셋업](control-plane.md) · [Traefik 셋업](../ingress/setup.md)

**목적:** OS만 설치된 새 서버를 기존 kubeadm 클러스터의 Worker로 등록합니다. Airflow용 Worker도 이 문서로 등록합니다.
**준비물:** 관리 호스트의 관리자 kubeconfig, CP1에서의 명령 실행([노드 명령 실행](../infrastructure/access.md#노드-명령-실행)), 새 서버에서 명령을 실행할 방법([가입 전 노드](../infrastructure/access.md#가입-전-노드)), 사내 미러 접근, 기존 CP1에서 검증된 registry 설정.
**실행 위치:** 단계 제목에 적습니다. 관리 호스트 블록은 저장소 루트에서 실행합니다. CP1에서 실행하는 블록은 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다. 새 Worker에서 실행하는 블록(2·4단계)은 그 서버가 아직 클러스터에 가입하지 않아 관리 호스트에서 닿지 않습니다. [가입 전 노드](../infrastructure/access.md#가입-전-노드) 절에 따라 블록을 문서 순서대로 사용자에게 전달해 실행 결과를 받고, 5단계의 `kubectl get node` 확인부터 이어서 진행합니다. 블록마다 새 셸(bash)입니다.

확인된 설치 기준은 **Ubuntu 22.04.2 LTS · Kubernetes 1.36.0 · containerd 2.2.1**입니다.
조회 근거와 남은 확인은 [서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)에 있습니다.

2단계의 [변경]은 아직 클러스터에 가입하지 않은 새 서버에만 해당합니다. 서비스 중인 노드의 kubelet·containerd 재시작과 `kubeadm reset`은 [승인] 대상이며 이 문서로 수행하지 않습니다.

## 1. 기존 설치 기준 확인 — 관리 호스트

[조회] [현재 환경 확인](baseline.md)의 1단계로 버전·노드·시스템 Pod를 조회하고, 설치 도구 후보도 확인합니다.

```bash
command -v kubeadm k3s rke2
```

[서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)의 기록과 기존 Worker의 조회([현재 환경 확인](baseline.md#2-설치-기준-조회--각-노드))로 OS·Kubernetes·런타임 버전, CRI·cgroup, CNI·MTU·필요한 통신, 패키지·이미지 미러를 확인합니다.
명령이 설치됐다는 사실만으로 구축 도구를 확정하지 않습니다. k3s·RKE2 등으로 관리하는 클러스터는 해당 제품의 Worker 가입 절차를 사용합니다.

## 2. 빈 서버에 프로그램 설치·설정 — 새 Worker

[새 서버 준비](prerequisites.md#1-노드-준비--각-새-노드)의 노드 준비 항목을 아래 2-1~2-4 명령으로 수행합니다.
**OS만 설치된 새 Ubuntu 22.04 amd64 Worker**에서 순서대로 실행하며 기존 Ready 노드에는 실행하지 않습니다.
kubeadm은 런타임과 kubelet을 자동 설치하지 않습니다.

[조회] 새 Worker에서 대상 서버가 맞는지 확인합니다. 이 절의 블록은 따로 적지 않으면 새 Worker에서 실행하며 [가입 전 노드](../infrastructure/access.md#가입-전-노드) 절에 따라 전달합니다.

```bash
cat /etc/os-release
uname -m
hostname
sudo test -e /etc/kubernetes/kubelet.conf && echo '이미 가입된 노드' || echo '가입 전'
```

**기대 결과:** Ubuntu 22.04, `x86_64`, 고유 hostname, `가입 전`이 표시됩니다. `이미 가입된 노드`면 2~4단계를 실행하지 않습니다.

### 2-0. 사용할 사내 미러와 준비 파일

- 패키지와 이미지는 [미러 원본](../infrastructure/repositories.md#패키지chartartifact-주소)의 Nexus 주소에서 받으며, 아래 명령에 그 주소를 직접 표기합니다. 공개 저장소로 직접 접속하지 않습니다.
- Kubernetes 경로는 원본의 `v1.36/deb/` 상대 경로를 미러 base에 이어 붙인 구성입니다. 사내 서버에서의 접속 성공 여부는 별도로 확인합니다.
- 미러 접근이 불가능하면 [파일 반입](../infrastructure/access.md#파일-반입) 절의 방법으로 의존성까지 포함한 패키지·이미지를 가져옵니다.
- Ubuntu 미러는 Ubuntu archive 서명을 보존하는 구성을 기준으로 합니다. 미러가 재서명한다면 미러의 서명 공개키를 같은 절의 방법으로 받아 `signed-by` 경로에 지정하고 [미러 원본](../infrastructure/repositories.md#패키지chartartifact-주소)에 기록합니다.
- 미러에서 받은 공개 서명키의 지문은 [미러 원본](../infrastructure/repositories.md#패키지chartartifact-주소)에 기록된 지문과 대조합니다. 기록이 없으면 2-2·2-4에 링크한 공식 설치 문서에 게시된 지문과 대조한 뒤 그 값을 같은 표에 기록합니다. 사내 CA·APT 인증이 필요하면 첫 `apt-get update` 전에 호스트 신뢰와 `auth.conf.d`를 준비하며, 인증값을 URL이나 Git에 넣지 않습니다.

**준비 파일:** 기존 CP1에서 검증된 registry별 `hosts.toml`·CA·인증 설정을 새 Worker의 `/var/tmp/worker-registry/`에 둡니다.
`registry.k8s.io/hosts.toml`, `docker.io/hosts.toml`처럼 원래 registry 이름별 디렉터리를 사용합니다. 비밀값은 Git에 넣지 않습니다.

1. [조회] CP1에서 registry 설정 폴더를 찾습니다. 1·2번의 블록은 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--script`로 CP1에 전달합니다.
   ```bash
   sudo grep -n 'config_path' /etc/containerd/config.toml
   sudo find /etc/containerd/certs.d -name hosts.toml
   ```
   `config_path` 값이 `<CP1 registry 설정 폴더>`입니다. 값이 `/etc/containerd/certs.d`가 아니면 그 경로로 `find`를 다시 실행해 `hosts.toml` 목록을 확인합니다.
2. [변경] CP1에서 그 폴더를 묶음 파일 하나로 만듭니다. 인증 설정이 들어 있을 수 있으므로 소유자만 읽는 파일을 먼저 만들고 그 안에 씁니다.
   ```bash
   install -m 0600 /dev/null /var/tmp/worker-registry.tgz
   sudo tar -C <CP1 registry 설정 폴더> -czf - . > /var/tmp/worker-registry.tgz
   ls -l /var/tmp/worker-registry.tgz
   ```
   성공: 권한 `-rw-------`이고 크기가 0이 아닌 파일이 표시됩니다.
3. [변경] CP1의 `/var/tmp/worker-registry.tgz`를 새 Worker의 `/var/tmp/worker-registry.tgz`로 옮깁니다. 새 Worker는 관리 호스트에서 닿지 않고 이 파일에는 인증 설정이 들어 있을 수 있어 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--copy`를 쓰지 않습니다. [가입 전 노드](../infrastructure/access.md#가입-전-노드) 절에 따라 두 경로를 전달하고 옮긴 결과를 받습니다. 관리 호스트를 거쳤다면 관리 호스트의 사본을 지웁니다.
4. [변경] 새 Worker에서 풉니다.
   ```bash
   sudo install -d -m 0700 /var/tmp/worker-registry
   sudo tar -C /var/tmp/worker-registry -xzf /var/tmp/worker-registry.tgz
   rm -f /var/tmp/worker-registry.tgz
   sudo find /var/tmp/worker-registry -name hosts.toml
   ```
   성공: 1번에서 본 것과 같은 `hosts.toml` 목록이 출력됩니다. CP1의 `/var/tmp/worker-registry.tgz`도 `python3 deploy/shared/scripts/node_exec.py <CP1 노드 이름> --context "<context>" --command 'rm -f /var/tmp/worker-registry.tgz'`로 지웁니다.

설치 명령은 전용 source 파일·빈 추가 source 디렉터리·전용 패키지 색인을 사용합니다.
각 `apt-get`·`apt-cache`에 `APT_MIRROR_OPTIONS`를 전달해 기존 공개 source나 오래된 색인을 사용하지 않습니다. 블록마다 새 셸이므로 이 배열을 쓰는 블록은 첫머리에서 다시 설정합니다.

### 2-1. 기본 설정

[변경] 새 Worker에서 실행합니다. swap을 끄고 재부팅 후 유지될 커널·네트워크 설정을 기록한 뒤 Ubuntu 미러 source를 등록합니다.

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

이 블록은 source 파일을 Ubuntu 미러 세 줄로 새로 씁니다. 2-2·2-4를 마친 뒤 다시 실행했다면 2-2·2-4의 저장소 등록 블록도 다시 실행합니다.

[조회] 새 Worker에서 결과를 확인합니다.

```bash
swapon --show
sysctl net.ipv4.ip_forward net.bridge.bridge-nf-call-iptables net.bridge.bridge-nf-call-ip6tables
dpkg-query -W -f='${Package}\t${Version}\n' ca-certificates curl gpg
```

**기대 결과:** `swapon --show`의 출력이 없고 세 sysctl 값이 `1`이며 세 패키지의 버전이 출력됩니다.

### 2-2. containerd 2.2.1 설치

[containerd 공식 안내](https://github.com/containerd/containerd/blob/release/2.2/docs/getting-started.md)의
Docker 배포 패키지를 사내 APT 미러에서 받습니다. `containerd.io`에는 runc도 포함됩니다.
[Ubuntu 저장소 등록 절차](https://docs.docker.com/engine/install/ubuntu/#install-using-the-apt-repository)의
패키지 서명 검증을 유지하며,
패키지 버전은 `2.2.1-1~ubuntu.22.04~jammy`로 고정합니다.

[변경] 새 Worker에서 서명키를 임시 파일로 받고 지문을 출력합니다.

```bash
curl -fsSL http://repository.samsungds.net/repository/proxy-apt-download.docker.com-linux-ubuntu/gpg \
  -o /tmp/worker-docker.asc
gpg --show-keys --with-fingerprint /tmp/worker-docker.asc
```

출력된 지문을 2-0에 적은 방법으로 Docker 공개키의 지문과 대조합니다. 다르면 멈추고 보고합니다. 그 키로 저장소를 등록하거나 패키지를 설치하지 않습니다.

[변경] 지문이 같으면 새 Worker에서 저장소를 등록하고 설치합니다.

```bash
APT_MIRROR_OPTIONS=(
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/worker-mirrors.list
  -o Dir::Etc::sourceparts=/etc/apt/worker-empty-sources
  -o Dir::State::lists=/var/lib/apt/lists-worker-mirrors
  -o APT::Update::Error-Mode=any
)

sudo install -m 0644 /tmp/worker-docker.asc /etc/apt/keyrings/worker-docker.asc

echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-docker.asc] http://repository.samsungds.net/repository/proxy-apt-download.docker.com-linux-ubuntu jammy stable' |
  sudo tee -a /etc/apt/sources.list.d/worker-mirrors.list

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y containerd.io=2.2.1-1~ubuntu.22.04~jammy
sudo apt-mark hold containerd.io
containerd --version
```

**기대 결과:** 마지막 줄에 `2.2.1`이 표시됩니다. 이 블록은 source 파일에 줄을 덧붙이므로, 다시 실행해야 하면 2-1 블록부터 다시 실행합니다.

### 2-3. containerd CRI·cgroup 설정

아래는 새 런타임의 초기 설정입니다. `/etc/containerd/config.toml`을 기본 설정으로 새로 쓰므로 이미 구성된 containerd에는 실행하지 않습니다.
이미 구성된 containerd가 있다면 기존 registry·CA·인증 설정을 덮어쓰지 말고 필요한 항목만 병합하며, 서비스 중인 노드의 containerd 재시작은 [승인] 대상입니다.
[containerd 2.x 설정 기준](https://v1-36.docs.kubernetes.io/docs/setup/production-environment/container-runtimes/#configuring-the-systemd-cgroup-driver)에
맞춰 CRI가 활성화된 기본 설정과 `SystemdCgroup = true`를 사용합니다.

[변경] 새 Worker에서 설정 파일을 만들고 registry 설정을 배치합니다. 둘째 `sed`는 기본 설정에 있는 registry 테이블의 `config_path` 값만 바꾸며 테이블을 새로 추가하지 않습니다.

```bash
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo sed -i "/^[[:space:]]*\[plugins\.'io\.containerd\.cri\.v1\.images'\.registry\]/,/^[[:space:]]*\[/ s|^\([[:space:]]*\)config_path = .*|\1config_path = '/etc/containerd/certs.d'|" /etc/containerd/config.toml

sudo install -d -m 0755 /etc/containerd/certs.d
sudo test -d /var/tmp/worker-registry
sudo cp -a /var/tmp/worker-registry/. /etc/containerd/certs.d/
```

설정 파일의 registry 항목은 다음과 같아야 합니다. 같은 TOML 테이블을 중복 추가하지 않습니다.

```toml
[plugins.'io.containerd.cri.v1.images'.registry]
  config_path = '/etc/containerd/certs.d'
```

[조회] 새 Worker에서 설정 결과를 확인합니다.

```bash
sudo grep -n 'SystemdCgroup' /etc/containerd/config.toml
sudo grep -n -A1 "^[[:space:]]*\[plugins\.'io\.containerd\.cri\.v1\.images'\.registry\]" /etc/containerd/config.toml
sudo find /etc/containerd/certs.d -name hosts.toml
```

**기대 결과:** `SystemdCgroup = true`, registry 테이블 바로 아래의 `config_path = '/etc/containerd/certs.d'`, `registry.k8s.io`·`docker.io`의 `hosts.toml`이 표시됩니다.
`config_path` 줄이 위 값이 아니면 기본 설정의 형식이 이 문서의 기준(containerd 2.2.1)과 다른 것입니다. containerd를 시작하지 않고 멈추고 `containerd --version`과 위 출력을 보고합니다.

`certs.d`에는 `registry.k8s.io`·`docker.io`와 기존 CNI 등이 사용하는 registry별 설정을 준비합니다.
Kubernetes 이미지용 주소는 `repository.samsungds.net/proxy-docker-registry.k8s.io/<이미지>:<태그>`이며,
실제 이미지 경로 변환과 인증은 기존 CP1에서 검증된 구성을 따릅니다.
[containerd registry 설정](https://github.com/containerd/containerd/blob/release/2.2/docs/hosts.md)에 따라
각 `hosts.toml`의 `server`도 사내 미러를 가리키게 해 공개 registry fallback을 방지합니다.
`pull`·`resolve` 권한, `/v2`·미러 prefix 경로, CA·인증을 확인합니다.
공개 registry를 `server`에 남기거나 TLS 검증을 끄지 않습니다.

[변경] 새 Worker에서 containerd를 시작합니다.

```bash
sudo systemctl enable --now containerd
sudo systemctl restart containerd
systemctl is-active containerd
```

**기대 결과:** `active`.

### 2-4. kubeadm·kubelet 1.36.0 설치

[Kubernetes 1.36 공식 설치 절차](https://v1-36.docs.kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)를
사용하되 kubeadm·kubelet 패키지를 `1.36.0-1.1`로 고정합니다.
kubelet 의존성으로 기본 CNI 실행 파일도 설치됩니다. 클러스터 CNI 구성은 기존 운영 설정을 유지합니다.

[변경] 새 Worker에서 서명키를 임시 파일로 받고 지문을 출력합니다.

```bash
curl -fsSL http://repository.samsungds.net/repository/proxy-raw-pkgs.k8s.io-core-stable/v1.36/deb/Release.key \
  -o /tmp/worker-kubernetes.key
gpg --show-keys --with-fingerprint /tmp/worker-kubernetes.key
```

출력된 지문을 2-0에 적은 방법으로 Kubernetes 공개키의 지문과 대조합니다. 다르면 멈추고 보고합니다. 그 키로 저장소를 등록하거나 패키지를 설치하지 않습니다.

[변경] 지문이 같으면 새 Worker에서 저장소를 등록하고 설치합니다.

```bash
APT_MIRROR_OPTIONS=(
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/worker-mirrors.list
  -o Dir::Etc::sourceparts=/etc/apt/worker-empty-sources
  -o Dir::State::lists=/var/lib/apt/lists-worker-mirrors
  -o APT::Update::Error-Mode=any
)

gpg --batch --yes --dearmor -o /tmp/worker-kubernetes.gpg /tmp/worker-kubernetes.key
sudo install -m 0644 /tmp/worker-kubernetes.gpg /etc/apt/keyrings/worker-kubernetes.gpg

echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/worker-kubernetes.gpg] http://repository.samsungds.net/repository/proxy-apt-pkgs.k8s.io-core-stable/v1.36/deb/ /' |
  sudo tee -a /etc/apt/sources.list.d/worker-mirrors.list

sudo apt-get "${APT_MIRROR_OPTIONS[@]}" update
sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y kubeadm=1.36.0-1.1 kubelet=1.36.0-1.1
sudo apt-mark hold kubeadm kubelet
sudo systemctl enable --now kubelet
```

이 블록도 source 파일에 줄을 덧붙이므로, 다시 실행해야 하면 2-1 블록부터 다시 실행합니다.

[조회] 설치 후 새 Worker에서 확인합니다.

```bash
APT_MIRROR_OPTIONS=(
  -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/worker-mirrors.list
  -o Dir::Etc::sourceparts=/etc/apt/worker-empty-sources
  -o Dir::State::lists=/var/lib/apt/lists-worker-mirrors
  -o APT::Update::Error-Mode=any
)

kubeadm version -o short
kubelet --version
containerd --version
systemctl is-active containerd
dpkg-query -W -f='${Package}\t${Version}\n' kubeadm kubelet containerd.io
apt-cache "${APT_MIRROR_OPTIONS[@]}" policy containerd.io kubeadm kubelet
```

`apt-cache policy`의 공급 주소가 사내 미러인지 확인합니다. 의존 패키지인 `cri-tools`·`kubernetes-cni`도
미러에 있어야 하며, 버전이나 패키지가 없으면 [파일 반입](../infrastructure/access.md#파일-반입) 절의 방법으로 가져옵니다.

[변경] 새 Worker에서 이미지를 받아 미러 접근을 검사합니다. 프로젝트의 metrics-server v0.9.0 이미지를 사내 주소로 받아 미러 접근을 확인한 뒤,
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

[변경] kubeadm으로 관리하는 기존 클러스터의 CP1에서 실행하며 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--command`로 전달합니다. 새 token이 만들어집니다.

```bash
sudo kubeadm token create --print-join-command
```

**기대 결과:** `kubeadm join <endpoint> --token … --discovery-token-ca-cert-hash …` 한 줄(**Worker용 가입 명령**)이 출력됩니다. 이 줄 전체가 4단계의 `<join 명령>`입니다. token은 4단계에서 새 Worker로 전달하는 것 말고는 응답·운영 기록·보고와 Git·공용 로그에 옮겨 적지 않습니다.
endpoint·CA hash를 임의로 바꾸지 않습니다. 출력된 endpoint가 [VIP와 backend](../infrastructure/network.md#vip와-backend)에 기록된 API VIP와 같은지 대조하며, 조회된 CP1 InternalIP로 대체하지 않습니다.

## 4. 클러스터 가입 — 새 Worker

실행 위치는 새 Worker이며 [가입 전 노드](../infrastructure/access.md#가입-전-노드) 절에 따라 블록을 전달합니다. `<join 명령>`은 3단계의 출력으로 채워 전달합니다. Worker용 명령에는 `--control-plane`이 없습니다. 기존 Ready 노드에 다시 join하지 않으며 새 Worker에서 `kubeadm init`을 실행하지 않습니다.

1. [조회] 새 Worker가 가입 전인지 확인합니다.
   ```bash
   sudo test -e /etc/kubernetes/kubelet.conf && echo '이미 가입된 노드' || echo '가입 전'
   ```
   `이미 가입된 노드`면 2번을 실행하지 않고 5단계의 조회로 갑니다.
2. [변경] 새 Worker에서 CP1이 출력한 `kubeadm join ...` 전체를 sudo로 실행합니다.
   ```bash
   sudo <join 명령>
   ```
   성공: `This node has joined the cluster`.

## 5. 등록·네트워크 확인 — 관리 호스트

[조회] `<새 Worker>`는 첫 명령의 `NAME` 열에 새로 나타난 노드 이름입니다.

```bash
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" get nodes -L kubernetes.io/hostname
kubectl --context "<context>" wait --for=condition=Ready "node/<새 Worker>" --timeout=300s
kubectl --context "<context>" -n kube-system get pods -o wide \
  --field-selector "spec.nodeName=<새 Worker>"
```

**기대 결과:** `node/<새 Worker> condition met`이 출력되고, 예상한 InternalIP·hostname으로 Ready이며, CNI 등 해당 노드의 시스템 Pod가 정상입니다.

**실패 확인:** NotReady이면 새 Worker에서 [조회]로 kubelet·containerd 로그와 CNI 상태를 확인합니다. 새 Worker가 노드 목록에 있으므로 블록을 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다. NotReady 때문에 `노드 명령 실패`나 대기 시간 초과로 끝나면 [가입 전 노드](../infrastructure/access.md#가입-전-노드) 절에 따라 전달합니다.

```bash
sudo journalctl -u kubelet -u containerd --since '15 min ago' --no-pager | tail -n 100
```

원인 확인 없이 reset·재가입하지 않습니다. `kubeadm reset`은 [승인] 대상입니다.

## 6. 클러스터 인수 확인 — 관리 호스트

새 클러스터를 구성했거나 새 Worker를 추가한 뒤 수행합니다.

[조회]

```bash
kubectl --context "<context>" get --raw='/readyz'
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" -n kube-system get pods -o wide
kubectl --context "<context>" -n kube-system get service kube-dns
kubectl --context "<context>" -n kube-system get pods -l component=etcd -o wide
```

[변경] 새 Worker에 고정한 시험 Pod 하나로 클러스터 DNS와 다른 노드의 Pod·Service 통신을 확인합니다. Pod는 명령이 끝나면 지워집니다. 클러스터 DNS domain이 기본값 `cluster.local`이 아니면 그 값으로 바꿉니다.

```bash
kubectl --context "<context>" -n default run worker-net-check --rm --attach --restart=Never \
  --image=repository.samsungds.net/proxy-docker-registry-1.docker.io/library/busybox:1.37.0 \
  --overrides='{"apiVersion":"v1","spec":{"nodeName":"<새 Worker>"}}' \
  -- nslookup kubernetes.default.svc.cluster.local
```

**기대 결과:** `Name:`과 `Address:` 줄이 출력되고 마지막 줄이 `pod "worker-net-check" deleted`로 시작합니다. 이름 해석이 실패하면 명령이 0이 아닌 코드로 끝납니다. Pod가 남았으면 `kubectl --context "<context>" -n default delete pod worker-net-check`로 지웁니다.

그 밖에 다음을 확인합니다.

- 사용할 저장소의 PVC 연결·파일 쓰기/읽기 성공: 이 Worker에 데이터를 두는 앱을 배포할 때 그 앱 가이드의 `C. 배포 후 확인`으로 확인합니다.
- Zot을 운영하는 클러스터에서는 새 Worker에서 [시험 이미지 CRI pull](../../../registry/docs/01-operations.md#수동-pushpull-시험) 성공
- API LB 상태 검사·backend 전환: [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법으로 확인합니다. etcd 상태는 위 [조회]의 etcd Pod가 제어면마다 `Running`인지로 봅니다. 운영 노드 중지는 포함하지 않습니다.

**완료 기준:** 새 Worker Ready, 시스템 Pod·클러스터 네트워크 정상, 설치 기준·원본 버전·실행 명령·인수 결과를 [서버·노드](../infrastructure/servers.md)에 기록.
Ready만으로 앱 접속까지 검증한 것으로 기록하지 않습니다. 새 노드 이름과 주소는 [별칭 표](../infrastructure/aliases.json)에도 추가합니다.

## 다음 단계

- Airflow: [서버 준비](../../../airflow/docs/01-prepare.md#서버-준비)에서 새 Worker의 DB·로그 디렉터리를 준비하고 env의 `NODE_NAME`을 조회한 `kubernetes.io/hostname` 값으로 지정합니다.
- 새 Worker를 외부 HTTPS 진입점으로도 쓸 때: 처음부터 backend를 지정해 설치하면 [Traefik 셋업](../ingress/setup.md), 운영 중 backend 추가는 [Traefik·VIP 확장](../ingress/expand.md).
- 기존 Traefik은 그대로 사용하며, Worker 추가만으로 앱이나 DB가 자동 이동하지 않습니다.

공식 참고: [Kubernetes 1.36 Linux Worker 추가](https://v1-36.docs.kubernetes.io/docs/tasks/administer-cluster/kubeadm/adding-linux-nodes/).
