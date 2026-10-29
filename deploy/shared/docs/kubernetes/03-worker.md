# 03. Worker 추가

[가이드 홈](README.md) · [CP1~3 셋업](01-control-plane.md) · [Traefik 셋업](02-traefik.md)

목표는 **OS만 설치된 새 서버를 기존 클러스터의 Worker로 등록하는 것**입니다.
기존 클러스터의 설치 방식과 버전을 먼저 확인합니다. 아래 가입 명령은 kubeadm 방식에 해당합니다.
Airflow용 Worker를 추가할 때도 이 문서만 따라 등록한 뒤 Airflow 배포 문서로 이동합니다.

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

kubeadm은 런타임과 kubelet을 자동 설치하지 않습니다.
OS·설치 버전이 미확인이라 공통 apt/dnf 설치 명령을 임의로 지정하지 않습니다.
[선택한 Kubernetes 버전의 설치 안내](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)와
[런타임 설정](https://kubernetes.io/docs/setup/production-environment/container-runtimes/)에 맞춰 설치합니다.
사내망은 승인된 미러 또는 버전·아키텍처·체크섬을 확인한 반입 패키지·이미지를 사용합니다.

설치 후 새 Worker에서 확인합니다.

```bash
kubeadm version -o short
kubelet --version
containerd --version
systemctl is-active containerd
```

kubelet은 join 전에 설정이 없어 재시작을 반복할 수 있습니다. join 이후 상태를 다시 확인합니다.
기록된 API VIP는 `10.172.26.148:6443`이며 실제 endpoint와 노드 간 통신 조건을 인프라 담당자와 확인합니다.

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

공식 참고: [Linux Worker 추가](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/adding-linux-nodes/).
