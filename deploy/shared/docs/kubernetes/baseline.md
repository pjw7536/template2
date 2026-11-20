# 현재 환경 확인

[가이드 홈](../README.md#클러스터) · 이전: [용어](concepts.md)

**목적:** 기존 클러스터와 노드의 상태를 조회해 설치·배포 기준을 확인합니다. 아래 명령은 설정을 변경하지 않습니다.
**준비물:** 관리 호스트의 kubeconfig와 조회 권한([Kubernetes API](../infrastructure/access.md#kubernetes-api)), 2단계는 각 노드의 SSH 접속([노드 SSH](../infrastructure/access.md#노드-ssh)).

## 1. 클러스터 조회 — 관리 호스트

[조회] 관리 호스트의 저장소 루트에서 실행합니다. `<context>`는 첫 명령의 `NAME` 열에 있는 이름입니다.

```bash
kubectl config get-contexts
kubectl --context "<context>" version -o yaml
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" get nodes -L kubernetes.io/hostname
kubectl --context "<context>" -n kube-system get pods -o wide
kubectl --context "<context>" get daemonsets -A
kubectl --context "<context>" get storageclass
kubectl --context "<context>" get pv
kubectl --context "<context>" get pvc -A
kubectl --context "<context>" get ingressclass
kubectl --context "<context>" get ingress -A
```

**기대 결과:** 노드명·IP·Ready가 [서버 목록](../infrastructure/servers.md)과 일치합니다. Worker의 ROLES는 `<none>`일 수 있습니다.

**실패 확인:**

- 명령이 없거나 권한이 부족하면 오류를 기록하고 [Kubernetes API](../infrastructure/access.md#kubernetes-api) 절의 방법으로 kubeconfig와 API 접근을 확인합니다.
- StorageClass가 없으면 정적 PV 사용 여부를 확인합니다.
- 노드 Ready만으로 앱·접속 상태를 판단하지 않습니다.

## 2. 설치 기준 조회 — 각 노드

새 서버를 구축하거나 기존 환경의 미확인 정보를 채울 때만 실행합니다.

[조회] 조회할 노드마다 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다. 설치되지 않은 명령·서비스는 오류를 내지만 나머지 명령은 계속 실행됩니다.

```bash
hostname
cat /etc/os-release
uname -r
uname -m
ip -brief address
ip route
nproc
free -h
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
df -hT
timedatectl status
swapon --show
command -v kubeadm kubelet kubectl containerd crictl k3s rke2
systemctl is-active containerd kubelet k3s k3s-agent rke2-server rke2-agent
```

설치되지 않은 후보 명령·서비스의 오류도 기록합니다. 명령 하나가 있다는 이유만으로 클러스터 구축 방식을 확정하지 않습니다.

| 확인할 정보 | 확인 방법 |
| --- | --- |
| OS·커널·CPU·메모리·디스크 | 위 블록의 각 노드 조회 |
| Kubernetes·런타임 버전, CRI·cgroup 설정 | 1단계의 `version`·`get nodes -o wide`와 노드의 런타임 설정 조회 |
| 설치 도구·CNI·CIDR·MTU·etcd 구성 | 1단계의 `kube-system` Pod·DaemonSet 목록과 제어면의 실행 설정 조회. 기록은 [클러스터 네트워크·실행 기반](../infrastructure/network.md#클러스터-네트워크실행-기반) |
| API/APP VIP backend·상태 검사·TLS 종료 위치 | [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법. 기록은 [VIP와 backend](../infrastructure/network.md#vip와-backend) |
| PV 경로·마운트·백업·StorageClass | 1단계의 `get storageclass`·`get pv`와 Worker의 `lsblk`·`df -hT` |
| SSH/sudo·Git·registry·배포 권한 | [접근 경로](../infrastructure/access.md)의 각 절에 있는 `찾는 방법` |

확인값은 [기록 규칙](../infrastructure/README.md#기록-규칙)에 따라 해당 주제의 원본에 반영합니다.
비밀번호·토큰·kubeconfig 내용은 기록하지 않습니다.

## 다음 단계

- 새 노드 구축: [새 서버 준비](prerequisites.md) → [CP1~3 셋업](control-plane.md) 또는 [Worker 추가](worker.md)
- 이미 Ready인 클러스터의 앱 배포: [앱 준비](../operations/02-deploy.md#배포-준비)
