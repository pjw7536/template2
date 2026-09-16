# 02. 빈 서버 준비

[가이드 홈](README.md) · 이전: [설치 기준 확인](01-baseline.md) · 다음: [클러스터 구축](03-cluster.md)

**적용 대상은 OS가 설치된 새 서버입니다. 기존 Ready 노드에 재설정하지 않습니다.**
현재 OS·런타임·CNI가 미확정이므로 아래는 준비 순서와 인수 조건입니다.
배포판별 패키지 설치, swap·커널·방화벽·런타임 설정 명령은 01장의 실제 기준을 확보한 뒤 추가해야 합니다.
이 문서만으로 아직 빈 서버 설치를 완료할 수는 없습니다.

## 1. 서버 이름·네트워크 — 모든 새 노드

인프라 담당자가 현황에 대응하는 역할별 서버를 준비합니다. 검증 환경은 운영 서버의 IP를 재사용하지 않습니다.
노드 이름, 고정 IP, 인터페이스, 기본 경로, DNS, 시간 서버, 프록시 사용 여부를 기록합니다.
OS 네트워크 설정은 확정된 배포판의 관리 방식으로 영구 적용합니다.

조회는 [01장의 노드 명령](01-baseline.md)을 다시 사용합니다.
**완료 기준:** 중복 없는 hostname/IP, 의도한 라우팅, DNS 이름 해석, 시간 동기화가 확인됩니다.
틀리면 패키지 설치보다 먼저 서버·네트워크 담당자가 수정합니다.

## 2. 통신표 — 인프라 담당자와 모든 새 노드

| 출발 | 도착 | 확인 내용 |
| --- | --- | --- |
| 운영 PC·CP1·노드 | API VIP → Control Plane | API endpoint 도달, 실제 API 포트와 LB backend |
| Control Plane 상호 | etcd·제어면 | 확인된 토폴로지의 필요한 통신 |
| Control Plane·Worker 상호 | kubelet·Pod 네트워크 | Kubernetes 및 선택한 CNI의 요구 포트·프로토콜 |
| 모든 노드 | DNS·시간 서버·registry·package mirror | 이름 해석, CA 신뢰, 인증, pull·패키지 접근 |
| 내 PC | APP VIP → 선택 Worker | 443 전달·상태 검사; 앱 준비 후 HTTPS 검증 |
| 앱 실행 노드·Pod | DB·스토리지·사내 OIDC 등 | 사용하는 연동의 주소·포트·권한 |

CIDR·CNI가 정해지지 않은 상태에서 방화벽 포트 전체 개방을 설치 절차로 삼지 않습니다.
Kubernetes 기본 통신과 CNI별 통신 요구사항은 별도로 확인합니다.
[공식 kubeadm 사전 준비](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/)를
기준으로 확인하되, 링크의 최신 버전을 현재 서버 버전으로 간주하지 않습니다.

## 3. 디스크·OS·런타임 — 모든 새 노드

1. OS 디스크와 앱 데이터 마운트의 용량·파일시스템·재부팅 후 마운트를 확인합니다.
2. 확정된 Kubernetes 버전에 맞춰 swap 정책과 커널·sysctl 요구사항을 적용합니다.
3. 승인된 런타임 패키지와 CRI 설정을 설치합니다. kubelet과 런타임의 cgroup 설정을 맞춥니다.
4. 사내 registry CA·mirror·인증을 노드 런타임에 설정합니다. 비밀 파일은 접근 제한된 경로에 둡니다.
5. 승인된 Kubernetes 도구 버전을 설치하고 자동 업데이트 정책을 정합니다.

swap 정책은 kubelet 설정과 함께 결정합니다. 런타임 설정 파일을 인터넷 예시로 통째로 덮어쓰지 않습니다.
Docker 이미지 목록에 보이는 이미지가 Kubernetes 런타임에도 등록됐다고 가정하지 않습니다.
[공식 런타임 안내](https://kubernetes.io/docs/setup/production-environment/container-runtimes/)에서
확인된 런타임 버전에 맞는 설정을 선택합니다.

**완료 기준:** 런타임 서비스 정상, CRI 사용 가능, 필요한 이미지 접근 가능, 디스크 마운트 정상입니다.
join 전 kubelet이 클러스터 설정을 기다리는 상태와 런타임 자체 실패를 구분합니다.
실패하면 해당 노드의 서비스 상태·로그와 DNS·CA·mirror 설정을 확인합니다.

## 4. 배포 도구 — CP1

Git·Bash·Make·Python 3.10+·kubectl·OpenSSL을 준비합니다. Helm 앱을 사용할 때는 각 앱의
`helm/chart.lock.json`과 README에 지정된 최소 Helm 버전·고정 chart를 추가합니다.
앱 이미지 빌드는 별도 빌드 환경에서 할 수 있으며 CP1에 Docker를 필수로 설치할 필요는 없습니다.

```bash
git --version
bash --version
make --version
python3 --version
kubectl version --client -o yaml
openssl version
```

Helm 앱을 선택했다면 `helm version --short`도 확인합니다.
**완료 기준:** 필요한 도구가 실행되고, 기준표에 버전·출처·설치 명령·재부팅 후 확인 결과가 기록됩니다.
이 조건과 01장의 설치 기준이 충족되면 03장으로 이동합니다.
