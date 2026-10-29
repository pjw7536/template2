# 01. CP1~3 셋업

[가이드 홈](README.md) · [Traefik 셋업](02-traefik.md) · [Worker 추가](03-worker.md)

목표는 **CP1에서 첫 제어면을 만들고 CP2·CP3를 같은 클러스터에 가입시키는 것**입니다.
이미 CP1~3가 운영 중이면 아래 조회만 수행하고 필요한 작업 문서로 이동합니다.
초기화 절차는 새 서버에만 적용합니다.

## 1. 설치 기준 확인 — 인프라 담당자

| 확인할 값 | 기준 |
| --- | --- |
| CP1·CP2·CP3 | 서로 다른 hostname·고정 IP·SSH/sudo 접근 |
| OS·CPU·Kubernetes 버전 | 세 서버의 실제 값과 설치할 패키지 버전 |
| 설치 도구 | kubeadm / k3s / RKE2 등 실제 운영 방식 |
| 런타임·네트워크 | CRI·cgroup 설정, CNI·Pod/Service CIDR·MTU |
| API endpoint | CP1~3의 API 포트로 전달하는 LB/VIP·인증서 대상 |
| 설치 파일 | 접근 가능한 패키지·이미지 미러와 CA·인증 |

현재 기록과 실제 값은 [서버 현황](../infrastructure/cluster.md)에서 대조합니다.
기록된 기존 API VIP는 `10.172.26.148:6443`입니다. 새 검증 환경에는 운영 IP를 재사용하지 않습니다.
기존 CP1에서 조회할 수 있다면 아래 명령을 사용합니다.

```bash
kubectl config get-contexts
read -r -p '기존 서버 context: ' KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" version -o yaml
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
command -v kubeadm k3s rke2
```

## 2. 각 서버에 기본 프로그램 설치 — CP1·CP2·CP3 각각

세 서버에서 다음 순서로 준비합니다.

1. hostname·고정 IP·DNS·시간 동기화·디스크·방화벽을 준비합니다.
2. 확정한 OS·Kubernetes 버전에 맞게 swap·커널·cgroup·통신 설정을 적용합니다.
3. containerd 등 승인된 CRI 런타임과 kubelet을 설치하고 registry 접근을 설정합니다.
4. kubeadm 방식이면 확정한 버전의 kubeadm을 설치합니다. CP1에는 kubectl도 준비합니다.

OS별 설치 명령은 아직 확정되지 않았습니다. 아래 결과와 설치 기준을 맞춘 뒤
[해당 Kubernetes 버전의 공식 설치 절차](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)를 사용합니다.
사내망은 승인된 미러나 버전·아키텍처·체크섬을 확인한 반입 파일을 사용합니다.

```bash
cat /etc/os-release
uname -m
kubeadm version -o short
kubelet --version
containerd --version
systemctl is-active containerd
```

이후 3~4단계는 **kubeadm과 CP별 로컬 etcd를 사용하는 새 클러스터 기준**입니다.
다른 설치 도구나 외부 etcd 방식이면 해당 구축 절차를 사용합니다.

## 3. 첫 제어면 초기화·CNI 설치 — 새 CP1

확정한 Kubernetes 버전으로 kubeadm 설정 파일을 준비합니다.
설정에는 API endpoint·CP1 주소·버전·이미지 저장소·CRI socket·인증서 SAN과
선택한 CNI에 맞는 Pod/Service CIDR·DNS domain을 반영합니다.
이 파일은 인프라 담당자가 준비하는 설치 입력이며 저장소에 완성된 설정이 있는 것은 아닙니다.

```bash
read -r -p '준비한 kubeadm 설정 파일 절대 경로: ' KUBEADM_CONFIG
sudo kubeadm init --config "$KUBEADM_CONFIG" --upload-certs
```

출력된 **Control Plane용 가입 명령**을 접근 제한된 위치에 보관합니다.
이 명령에는 token·CA hash·`--control-plane`·`--certificate-key`가 포함됩니다.
토큰·certificate key·관리자 kubeconfig는 Git이나 공용 로그에 올리지 않습니다.

CP1에서 확정한 CNI를 해당 제품의 설치 절차로 한 번 설치합니다.
CNI 설정은 kubeadm의 네트워크 설정과 일치해야 합니다.
CNI 설치 전의 NotReady를 이유로 init을 반복하지 않습니다.

## 4. 나머지 제어면 가입 — 새 CP2 → 새 CP3

각 서버에서 2단계가 끝났는지 확인한 뒤,
CP1이 출력한 **Control Plane용 `sudo kubeadm join ...` 명령**을 CP2, CP3에 한 대씩 실행합니다.
API LB의 CP1~3 backend와 상태 검사도 확인합니다.
가입 정보가 만료됐으면 인프라 담당자가 새 token·인증서 공유 정보를 발급합니다.

## 5. 상태 확인 — CP1

최초 확인은 생성된 관리자 kubeconfig로 수행합니다.

```bash
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get --raw='/readyz'
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf get nodes -o wide
sudo kubectl --kubeconfig /etc/kubernetes/admin.conf -n kube-system get pods -o wide
```

**완료:** API가 `ok`이고 CP1~3가 Ready이며 각 제어면의 API server·etcd 등 시스템 Pod가 정상입니다.
Worker가 아직 없다면 CoreDNS 같은 일반 Pod는 Worker 등록 후 준비 상태를 확인합니다.
관리용 kubeconfig·context는 CP1 배포 계정에도 해당 권한 정책에 맞춰 준비합니다.

이제 [03. Worker 추가](03-worker.md)로 최소 한 대를 등록한 뒤 [02. Traefik 셋업](02-traefik.md)을 진행합니다.

상세 근거: [kubeadm HA 구성](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/).
