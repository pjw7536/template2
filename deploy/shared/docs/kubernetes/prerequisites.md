# 새 서버 준비

[가이드 홈](../README.md#클러스터) · [CP1~3 셋업](control-plane.md) · [Worker 추가](worker.md)

**목적:** OS가 설치된 새 노드의 공통 준비 조건·통신·배포 도구를 확인합니다. 현재 Ready 노드는 재설정하지 않습니다.
**준비물:** 확정된 OS·Kubernetes·런타임 버전, 인프라 담당자의 네트워크·스토리지 정보.

- 확인된 설치 기준은 [서버 현황](../infrastructure/servers.md#확인된-worker-설치-기준)에 있습니다.
- Ubuntu 22.04.2 LTS amd64·Kubernetes 1.36.0·containerd 2.2.1의 설치 명령은 [Worker 추가](worker.md#2-빈-서버에-프로그램-설치설정--새-worker)에 있습니다.
- CNI·CIDR·MTU·실제 CRI 및 registry 설정과 제어면별 설치 기준은 대상 환경에서 별도로 확인합니다.

## 1. 노드 준비 — 인프라 담당자·각 새 노드

1. 중복 없는 hostname·고정 IP, 라우팅·DNS·시간 동기화를 준비합니다.
2. OS·앱 데이터 디스크의 용량·권한·재부팅 후 마운트를 확인합니다.
3. 확정된 Kubernetes 버전에 맞게 swap·커널·sysctl·cgroup을 설정합니다.
4. 승인된 CRI 런타임(containerd 등)과 kubelet·kubeadm을 설치합니다. kubelet과 런타임의 cgroup 설정을 맞춥니다.
5. 노드 런타임의 registry CA·인증·mirror와 필요한 이미지 접근을 확인합니다.

패키지·이미지·고정 chart는 승인된 미러 또는 외부 반입 환경에서 준비합니다. 사내 서버의 인터넷 연결을 가정하지 않으며,
반입할 때는 버전·CPU 아키텍처·체크섬을 확인합니다. Helm chart와 컨테이너 이미지는 각각 반입해야 하며,
Docker에 넣은 이미지는 Kubernetes가 사용하는 containerd에 별도로 넣어야 할 수 있습니다.

**기대 결과:** 재부팅 후에도 주소·디스크 마운트가 유지되고, 런타임 CRI가 활성화되며, 새 노드 런타임에서 필요한 이미지를 받을 수 있습니다.

## 2. 필요한 통신

| 출발 → 도착 | 확인 내용 |
| --- | --- |
| 관리 PC·노드 → API VIP → Control Plane | API 포트·LB backend |
| Control Plane 상호 | 실제 etcd·제어면 구성에 필요한 통신 |
| Control Plane·Worker 상호 | kubelet·선택한 CNI의 포트·프로토콜 |
| 모든 노드 → DNS·시간 서버·registry·mirror | 이름 해석·CA·인증·접근 |
| 사용자 PC → APP VIP → Worker | 443 전달·상태 검사 |
| 앱 → DB·스토리지·OIDC | 앱별 연동 주소·포트·권한 |

포트·OS 설정은 확정된 설치 버전과 CNI 요구사항으로 결정합니다. 검증 환경에 운영 IP를 재사용하지 않습니다.

## 3. 배포 도구 — CP1

Git·Bash·Make·Python 3.10+·kubectl·OpenSSL을 준비합니다.
Helm 앱은 각 앱의 README와 `helm/chart.lock.json`에 맞는 Helm·chart가 필요합니다. 이미지 빌드는 별도 환경에서 수행할 수 있습니다.

```bash
git --version
bash --version
make --version
python3 --version
kubectl version --client -o yaml
openssl version
helm version --short   # Helm 앱을 배포할 때만
```

**기대 결과:** 각 명령이 버전을 출력합니다. 명령이 없으면 승인된 패키지로 설치를 요청합니다.

## 완료 기준과 다음 단계

네트워크·디스크·런타임·CRI·이미지 접근·필수 도구가 정상이며, 적용한 버전과 설치 명령이 기록되어 있습니다.
다음은 [CP1~3 셋업](control-plane.md) 또는 [Worker 추가](worker.md)입니다.
