# CP1~3 셋업

[가이드 홈](../README.md#클러스터) · [새 서버 준비](prerequisites.md) · [Worker 추가](worker.md) · [Traefik 셋업](../ingress/setup.md)

**목적:** CP1에서 첫 제어면을 만들고 CP2·CP3를 같은 클러스터에 가입시킵니다. 초기화 절차는 새 서버에만 적용합니다.
이미 CP1~3가 운영 중이면 [현재 환경 확인](baseline.md)만 수행하고 필요한 작업 문서로 이동합니다.
**준비물:** [새 서버 준비](prerequisites.md)를 마친 CP1·CP2·CP3, 3단계의 kubeadm 설정 파일, 세 서버의 SSH 접속과 sudo([노드 SSH](../infrastructure/access.md#노드-ssh)).
**실행 위치:** 단계 제목에 적습니다. 제어면에서 실행하는 블록은 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 블록 전체를 그 서버의 셸에 전달하며 블록마다 새 셸입니다. 관리 호스트 블록은 저장소 루트에서 실행합니다.

1~5단계의 [변경]은 아직 서비스하지 않는 새 서버에만 해당합니다. 운영 중인 클러스터의 `kubeadm init`·`kubeadm reset`과 서비스 중인 노드의 kubelet·containerd·API server 재시작은 [승인] 대상이며 이 문서로 수행하지 않습니다.

## 1. 설치 기준 확인

[조회] 아래 값을 기록과 대조합니다. 명령은 없습니다.

| 확인할 값 | 기준 |
| --- | --- |
| CP1·CP2·CP3 | 서로 다른 hostname·고정 IP·SSH/sudo 접근 |
| OS·CPU·Kubernetes 버전 | 세 서버의 실제 값과 설치할 패키지 버전 |
| 설치 도구 | kubeadm / k3s / RKE2 등 실제 운영 방식 |
| 런타임·네트워크 | CRI·cgroup 설정, CNI·Pod/Service CIDR·MTU |
| API endpoint | CP1~3의 API 포트로 전달하는 LB/VIP·인증서 대상 |
| 설치 파일 | 접근 가능한 패키지·이미지 미러와 CA·인증 |

- 기록된 노드와 버전은 [서버 현황](../infrastructure/servers.md), API VIP는 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로), CNI·CIDR은 [클러스터 네트워크·실행 기반](../infrastructure/network.md#클러스터-네트워크실행-기반), 미러는 [저장소·미러](../infrastructure/repositories.md)와 대조합니다.
- 기존 CP1에서 조회할 수 있다면 [현재 환경 확인](baseline.md)의 1단계를 실행합니다.
- 새 검증 환경에는 운영 IP를 재사용하지 않습니다.

## 2. 기본 프로그램 설치 — CP1·CP2·CP3 각각

1. [변경] [새 서버 준비](prerequisites.md#1-노드-준비--각-새-노드)의 노드 준비를 마칩니다.
2. [변경] 확인된 기준(Ubuntu 22.04.2 LTS amd64·Kubernetes 1.36.0·containerd 2.2.1)이 같다면 [Worker 추가](worker.md#2-빈-서버에-프로그램-설치설정--새-worker)의 2-1~2-4 블록으로 런타임과 kubeadm·kubelet을 설치합니다.
3. [변경] CP1에는 같은 버전의 kubectl도 설치합니다. 2-4를 마친 CP1에서 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.
   ```bash
   APT_MIRROR_OPTIONS=(
     -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/worker-mirrors.list
     -o Dir::Etc::sourceparts=/etc/apt/worker-empty-sources
     -o Dir::State::lists=/var/lib/apt/lists-worker-mirrors
     -o APT::Update::Error-Mode=any
   )
   sudo apt-get "${APT_MIRROR_OPTIONS[@]}" install -y --allow-downgrades kubectl=1.36.0-1.1
   sudo apt-mark hold kubectl
   kubectl version --client
   ```
   성공: `Client Version: v1.36.0`. kubeadm의 의존성으로 다른 버전의 kubectl이 이미 설치됐어도 `--allow-downgrades`가 같은 버전으로 맞춥니다.

제어면별 OS·버전이 위 기준과 다르면 [해당 Kubernetes 버전의 공식 설치 절차](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)를 사용합니다.
제어면의 설치 기준은 [서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)의 남은 확인 항목입니다.

[조회] 세 서버에서 각각 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

```bash
cat /etc/os-release
uname -m
kubeadm version -o short
kubelet --version
containerd --version
systemctl is-active containerd
```

**기대 결과:** 세 서버의 버전이 설치 기준과 같고 containerd가 `active`입니다.

이후 3~4단계는 **kubeadm과 CP별 로컬 etcd를 사용하는 새 클러스터 기준**입니다.
다른 설치 도구나 외부 etcd 방식이면 해당 구축 절차를 사용합니다.

## 3. 첫 제어면 초기화·CNI 설치 — 새 CP1

**입력:** kubeadm 설정 파일. API endpoint·CP1 주소·버전·이미지 저장소·CRI socket·인증서 SAN과
선택한 CNI에 맞는 Pod/Service CIDR·DNS domain을 반영합니다. 저장소에 완성된 설정은 없습니다.
값은 1단계의 기록에서 읽어 파일을 비대화형으로 작성하고, [노드 SSH](../infrastructure/access.md#노드-ssh)의 파일 전송 방법으로 CP1의 `<kubeadm 설정 파일>` 경로에 둡니다.
CNI·CIDR처럼 기록에 값이 없는 항목이 있으면 멈추고 그 항목을 보고합니다. 값을 추정해 초기화하지 않습니다.

1. [조회] CP1이 초기화 전인지 확인합니다.
   ```bash
   sudo test -e /etc/kubernetes/admin.conf && echo '이미 초기화된 제어면' || echo '초기화 전'
   ```
   `이미 초기화된 제어면`이면 2~4번을 실행하지 않고 [5단계](#5-상태-확인--cp1)의 조회로 갑니다.
2. [검사] 설정 파일을 검사합니다. 클러스터를 만들지 않습니다.
   ```bash
   sudo kubeadm config validate --config <kubeadm 설정 파일>
   ```
   성공: 오류 없이 끝납니다(종료 코드 0).
3. [변경] 첫 제어면을 초기화합니다.
   ```bash
   sudo kubeadm init --config <kubeadm 설정 파일> --upload-certs
   ```
   **기대 결과:** `Your Kubernetes control-plane has initialized successfully!`와 token·CA hash·`--control-plane`·`--certificate-key`가 포함된 **Control Plane용 가입 명령**이 출력됩니다.
   출력의 token·certificate key는 응답·운영 기록·보고에 옮겨 적지 않습니다. 가입 명령은 4단계에서 다시 발급하므로 따로 보관하지 않습니다. 관리자 kubeconfig는 Git이나 공용 로그에 올리지 않습니다.
4. [변경] CP1에서 확정한 CNI를 해당 제품의 설치 절차로 한 번 설치합니다. CNI 설정은 kubeadm의 네트워크 설정과 일치해야 합니다. 설치 파일은 사내 미러에서 받고 없으면 [파일 반입](../infrastructure/access.md#파일-반입) 절로 가져옵니다. 결과는 5단계의 조회로 확인합니다.

CNI 설치 전에는 노드가 NotReady일 수 있으며, 이를 이유로 init을 반복하지 않습니다.

## 4. 나머지 제어면 가입 — 새 CP2 → 새 CP3

각 서버에서 2단계를 마친 뒤 CP2, CP3 순서로 한 대씩 진행합니다. CP1과 가입할 서버에서 실행하는 블록은 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

1. [조회] 가입할 서버가 가입 전인지 확인합니다. 실행 위치는 가입할 서버입니다.
   ```bash
   sudo test -e /etc/kubernetes/kubelet.conf && echo '이미 가입된 노드' || echo '가입 전'
   ```
   `이미 가입된 노드`면 그 서버에는 `join`을 실행하지 않습니다.
2. [변경] CP1에서 Control Plane용 가입 명령을 발급합니다. 인증서를 다시 올리고 새 token을 만듭니다.
   ```bash
   sudo kubeadm token create --print-join-command \
     --certificate-key "$(sudo kubeadm init phase upload-certs --upload-certs | tail -n 1)"
   ```
   성공: `kubeadm join <endpoint> --token … --discovery-token-ca-cert-hash … --control-plane --certificate-key …` 한 줄이 출력됩니다. 이 줄 전체가 `<join 명령>`입니다. 응답·운영 기록·보고에 옮겨 적지 않습니다.
3. [변경] 가입할 서버에서 그 명령을 sudo로 실행합니다.
   ```bash
   sudo <join 명령>
   ```
   성공: `This node has joined the cluster and a new control plane instance was created`.
4. [조회] [5단계](#5-상태-확인--cp1)의 블록으로 새 제어면이 Ready인지 확인한 뒤 다음 서버로 갑니다.

API LB의 CP1~3 backend와 상태 검사는 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법으로 확인하고 설정합니다.

**실패 확인:** 가입 정보가 만료됐으면(token 24시간, certificate key 2시간) 2번을 다시 실행해 새로 발급합니다. 이미 등록된 노드에 `join`을 다시 실행하지 않습니다.

## 5. 상태 확인 — CP1

[조회] CP1에서 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

```bash
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get --raw='/readyz'
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get nodes -o wide
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf -n kube-system get pods -o wide
```

**기대 결과:** API가 `ok`이고 CP1~3가 Ready이며 각 제어면의 API server·etcd 등 시스템 Pod가 정상입니다.
Worker가 아직 없다면 CoreDNS 같은 일반 Pod는 Worker 등록 후 확인합니다.

**실패 확인:** 권한 부족으로 조회가 실패한 경우와 서비스 자체의 장애를 구별합니다.

관리용 kubeconfig·context는 [관리 호스트 준비](../operations/04-drift.md#관리-호스트-준비)에 따라 관리 호스트 배포 계정에 둡니다.

## 다음 단계

1. [Worker 추가](worker.md)로 최소 한 대를 등록하고 [클러스터 인수 확인](worker.md#6-클러스터-인수-확인--관리-호스트)을 수행합니다.
2. [공용 Traefik](../../ingress/README.md)을 설치합니다. VIP backend를 지정하려면 [Traefik 셋업](../ingress/setup.md)을 따릅니다.
3. 필요하면 아래 [metrics-server 설치](#metrics-server-설치)와 [API server OIDC 인증](oidc.md)을 진행합니다.

상세 근거: [kubeadm HA 구성](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/).

## metrics-server 설치

**목적:** 클러스터 공용 Metrics API를 제공해 `kubectl top`과 Headlamp 등에서 CPU·메모리 수치를 확인합니다.
**준비물:** 관리자 권한의 context, 저장소 루트의 [설치 YAML](../../metrics-server/components.yaml).
**실행 위치:** 관리 호스트의 저장소 루트.

- 설치 YAML은 공식 v0.9.0 구성을 포함하며 서버는 GitHub에 접속하지 않습니다.
- 이미지: `repository.samsungds.net/proxy-docker-registry.k8s.io/metrics-server/metrics-server:v0.9.0`
- v0.9.x는 Kubernetes 1.34 이상을 지원합니다. 참고: [v0.9.0 릴리스](https://github.com/kubernetes-sigs/metrics-server/releases/tag/v0.9.0), [설치 요구사항](https://github.com/kubernetes-sigs/metrics-server#requirements).
- **남은 확인:** 대상 API server 버전은 1.36.4와 [서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)의 확인값 v1.36.0이 일치하지 않습니다. 1단계 `version` 출력으로 실제 버전을 확인해 서버 현황에 반영합니다. 두 값 모두 지원 범위입니다.
- 설치 YAML은 `--kubelet-insecure-tls`를 사용합니다. 노드 인증서의 IP SAN 누락으로 수집이 실패하는 환경에서 모든 kubelet 서버 인증서 검증을 생략합니다. 노드 인증서를 정상화한 뒤에는 이 옵션을 제거하고 같은 명령으로 재적용합니다.

### 1. 기존 설치 확인 — 관리 호스트

[조회]

```bash
kubectl --context "<context>" version
kubectl --context "<context>" get apiservice v1beta1.metrics.k8s.io
kubectl --context "<context>" -n kube-system get deployment metrics-server
```

APIService와 Deployment가 모두 `NotFound`이면 2단계로 진행합니다.
기존 리소스가 있으면 현재 설치 도구와 상태를 먼저 확인합니다. 이 저장소 YAML로 설치한 경우 2단계를 다시 실행하면 변경된 설정이 반영되고 Pod가 교체됩니다.
미러 인증이 필요하면 `kube-system`의 이미지 인증 Secret을 준비하고 설치 YAML의 Deployment에 `spec.template.spec.imagePullSecrets`로 연결합니다.

### 2. 설치·재적용 — 관리 호스트의 저장소 루트

[변경] 설치하거나 다시 적용합니다. 명령이 Deployment와 APIService 준비를 각각 최대 180초 기다립니다.

```bash
make metrics-server-up KUBE_CONTEXT="<context>"
```

성공: `deployment "metrics-server" successfully rolled out`과 `apiservice.apiregistration.k8s.io/v1beta1.metrics.k8s.io condition met`.

[조회] 수치를 확인합니다.

```bash
kubectl --context "<context>" top nodes
kubectl --context "<context>" top pods -A
```

**기대 결과:** `top`에 수치가 표시됩니다. 첫 수집 전에는 수치가 없을 수 있으므로 잠시 후 다시 확인합니다.

**실패 확인:** [조회]

```bash
kubectl --context "<context>" -n kube-system describe pods -l k8s-app=metrics-server
kubectl --context "<context>" -n kube-system logs deployment/metrics-server --tail=100
kubectl --context "<context>" describe apiservice v1beta1.metrics.k8s.io
kubectl --context "<context>" -n kube-system get deployment metrics-server \
  -o jsonpath='{.spec.template.spec.containers[0].args}{"\n"}'
```

- `ImagePullBackOff`: 이벤트의 이미지가 위 사내 미러 주소인지와 미러 인증·노드 CA를 확인합니다.
- kubelet `x509` 오류가 계속되면 최신 YAML을 재적용한 뒤 실제 Deployment 인자에 `--kubelet-insecure-tls`가 있는지 확인합니다.
