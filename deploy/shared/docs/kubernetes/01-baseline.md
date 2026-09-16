# 01. 현재 환경 조회와 준비물

[가이드 홈](README.md) · 이전: [전체 그림](00-concepts.md) · 다음: [서버 준비](02-servers.md)

이 장은 기존 서버에서 **읽기 전용으로** 사실을 확인합니다. 설치·재시작·join은 수행하지 않습니다.
배포 계정의 kubectl 조회 권한과 노드 SSH 권한을 준비합니다. 명령이 없거나 권한이 없으면 오류를 기록하고
담당자에게 해당 항목을 요청합니다. 확인 목적으로 기존 서버에 패키지를 설치하지 않습니다.

## 1. 클러스터 확인 — CP1

임의 디렉터리에서 실행할 수 있습니다. context 이름은 첫 명령 결과에서 선택합니다.

```bash
kubectl config get-contexts
read -r -p '조회할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" version -o yaml
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$KUBE_CONTEXT" get nodes -o custom-columns='NAME:.metadata.name,OS:.status.nodeInfo.osImage,KERNEL:.status.nodeInfo.kernelVersion,KUBELET:.status.nodeInfo.kubeletVersion,RUNTIME:.status.nodeInfo.containerRuntimeVersion,PODCIDR:.spec.podCIDR'
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
kubectl --context "$KUBE_CONTEXT" get daemonsets -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,IMAGES:.spec.template.spec.containers[*].image'
kubectl --context "$KUBE_CONTEXT" get storageclass
kubectl --context "$KUBE_CONTEXT" get pv
kubectl --context "$KUBE_CONTEXT" get pvc -A
kubectl --context "$KUBE_CONTEXT" get ingressclass
kubectl --context "$KUBE_CONTEXT" get ingress -A
```

기대값 대신 실제 조회 결과를 기록합니다.
노드는 [현황 표](../infrastructure/cluster.md)의 5대와 비교하고 추가·누락·InternalIP 차이를 기록합니다.
Worker의 ROLES가 `<none>`이어도 그 자체로 이상은 아닙니다. 역할은 현황과 라벨을 함께 확인합니다.
CNI 후보는 DaemonSet과 시스템 Pod에서 찾되 이름만으로 설정·버전을 확정하지 않습니다.
StorageClass가 없어도 기존 정적 PV를 사용할 수 있습니다. 동적 공급이 가능하다고 해석하지 않습니다.

## 2. OS·런타임 확인 — 5대 각각

각 노드에 SSH로 접속해 서버 이름과 함께 기록합니다. systemd 계열 Linux의 조회 명령입니다.

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

후보를 함께 조회하므로 설치되지 않은 명령·서비스가 있으면 종료 코드가 0이 아닐 수 있습니다.
존재하는 서비스와 오류를 구분합니다. containerd가 있으면 `containerd --version`,
kubeadm이 있으면 `kubeadm version -o short`도 확인합니다.
도구의 존재만으로 해당 도구로 구축했다고 확정하지 않습니다.

## 3. 관리자에게 확인할 항목

클러스터 관리자에게 다음 표의 미확인 항목을 확인합니다. kubeadm 구축이 확인되면
CP1에서 아래 ConfigMap의 존재를 조회하고 관리자가 내용을 확인해 버전·네트워크 설정을 기록합니다.
ConfigMap이나 노드 설정 파일 전체를 공용 작업 로그에 붙여 넣지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n kube-system get configmap kubeadm-config
```

| 항목 | 기록할 내용 | 확인 근거 |
| --- | --- | --- |
| OS·커널 | 노드별 배포판·버전 | OS 조회 |
| Kubernetes | API server·kubelet·kubectl 버전 | version·nodes |
| 구축 방식 | kubeadm / K3s / 기타와 구축 기록 위치 | 관리자·구축 기록 |
| 런타임 | 종류·버전·CRI socket·cgroup driver | 노드 설정 |
| CNI | 제품·버전·설치 방법·설정·필요 포트 | 관리자·실행 설정 |
| 네트워크 | Pod CIDR·Service CIDR·DNS domain·MTU | 관리자·구축 설정 |
| API VIP | endpoint·LB backend·상태 검사 | 인프라 담당자 |
| APP VIP·DNS | backend·TLS 종료 위치·이름 해석·상태 검사 | 인프라 담당자 |
| 디스크 | 마운트·용량·PV 연결·백업 위치 | Worker·스토리지 담당자 |
| 인증·권한 | SSH/sudo·Git·registry·클러스터 작업 담당 | 각 관리자, 인증값은 기록하지 않음 |

## 4. 설치 기준 기록표

위 조회 결과는 아래 양식으로 정리해 [공통 현황](../infrastructure/cluster.md)의 설치 기준을 갱신합니다.
공개 기록에는 인증값을 넣지 않습니다. 설치용 전체 설정은 담당자가 접근 제한된 외부 경로로 보관합니다.

| 항목 | 확인값 | 확인일·근거 | 담당자 | 상태 |
| --- | --- | --- | --- | --- |
| 노드 구성 | 현황 문서 참조 | 2026-09-16 사용자 확인 | 운영 담당 | 확인 |
| OS·버전·설치 도구 | 미확인 | 서버 조회 필요 | 인프라 담당 | 대기 |
| 런타임·CNI·CIDR | 미확인 | 서버 조회 필요 | 인프라 담당 | 대기 |
| API·APP VIP의 실제 설정 | 기존 기록과 대조 필요 | LB 조회 필요 | 네트워크 담당 | 대기 |
| 이미지·패키지·차트 반입 | 앱별 목록과 승인 경로 | 반입 확인 필요 | 배포 담당 | 대기 |

## 5. 반입물과 담당 경계

인터넷 접근이 가능한 준비 환경과 사내 배포 서버를 구별합니다. 사내 서버에서 외부 다운로드가 된다고 가정하지 않습니다.

| 준비물 | 준비 위치·담당 | 반입 후 확인 |
| --- | --- | --- |
| OS 패키지·런타임·Kubernetes·CNI | 인프라 담당의 승인 mirror 또는 반입 환경 | 버전·아키텍처·checksum·의존 패키지 |
| Git·Bash·Make·Python·kubectl·OpenSSL | CP1 도구 준비 담당 | 실행 가능 여부와 앱 요구 버전 |
| Helm·고정 chart | Airflow·Monitoring·Headlamp 안내의 준비 환경 | 각 앱 chart.lock.json과 checksum |
| 컨테이너 이미지 | 빌드 환경 → 사내 registry 또는 런타임 반입 | 정확한 tag/digest·노드 pull 가능 여부 |
| DNS·VIP·포트·인증서 | 인프라·인증서 담당 | 발급 완료, 도메인·만료·체인 확인 |

**완료 기준:** 기존 앱 배포는 context·노드·필요 앱의 저장소/네트워크를 확인하고 04장으로 이동합니다.
빈 서버 구축은 설치 기준표의 OS·설치 도구·런타임·CNI·CIDR·VIP를 모두 확정해야 02~03장을 실행 절차로 완성할 수 있습니다.
