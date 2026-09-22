# 01. 현재 환경 확인

[가이드 홈](README.md) · 이전: [용어](00-concepts.md) · 다음: [앱 준비](04-prerequisites.md)

기존 서버에서 읽기 전용으로 확인합니다. 명령·권한이 없으면 오류를 기록하고 담당자에게 요청합니다.

## CP1에서 클러스터 조회

```bash
kubectl config get-contexts
read -r -p '조회할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" version -o yaml
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
kubectl --context "$KUBE_CONTEXT" get daemonsets -A
kubectl --context "$KUBE_CONTEXT" get storageclass
kubectl --context "$KUBE_CONTEXT" get pv
kubectl --context "$KUBE_CONTEXT" get pvc -A
kubectl --context "$KUBE_CONTEXT" get ingressclass
kubectl --context "$KUBE_CONTEXT" get ingress -A
```

[현재 5대 목록](README.md#현재-서버-상황)과 노드명·IP·Ready를 비교합니다.
Worker의 ROLES가 `<none>`이어도 그 자체로 이상은 아닙니다.
StorageClass가 없으면 정적 PV 사용 여부를 확인합니다. 노드 Ready만으로 앱·접속 상태를 판단하지 않습니다.

## 설치 기준이 필요하면 각 노드에서 조회

새 서버를 구축하거나 기존 환경의 미확인 정보를 채울 때 사용합니다.

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

설치되지 않은 후보 서비스·명령의 오류는 따로 기록합니다. 도구 이름만으로 구축 방식을 확정하지 않습니다.

| 확인할 정보 | 근거·담당 |
| --- | --- |
| OS·커널·CPU·메모리·디스크 | 각 노드 조회 |
| Kubernetes·런타임 버전, CRI·cgroup 설정 | version·노드 설정 |
| 설치 도구·CNI·CIDR·MTU·etcd 구성 | 인프라 담당자의 구축 기록·실행 설정 |
| API/APP VIP backend·상태 검사·TLS 종료 위치 | 네트워크 담당자의 실제 LB 설정 |
| PV 경로·마운트·백업·StorageClass | Worker·스토리지 담당자 |
| SSH/sudo·Git·registry·배포 권한 | 각 관리자 |

확인값은 `값 / 확인일 / 근거 / 담당자 / 미해결 항목`으로 [현황 원본](../infrastructure/cluster.md)에 기록합니다.
비밀번호·토큰·kubeconfig 내용은 기록하지 않습니다.

**다음 단계:** 기존 앱 배포는 context·노드·앱 저장소/네트워크 확인 후 [04장](04-prerequisites.md)으로 이동합니다.
새 서버 구축은 설치 도구·버전·런타임·CNI·CIDR·VIP를 확정한 뒤 [02장](02-servers.md)으로 이동합니다.
