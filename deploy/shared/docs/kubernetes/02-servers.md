# 02. 새 서버 준비

[가이드 홈](README.md) · 이전: [환경 확인](01-baseline.md) · 다음: [클러스터 구축](03-cluster.md)

**OS가 설치된 새 서버용 준비 목록입니다. 현재 Ready 노드는 재설정하지 않습니다.**
OS·설치 도구·버전·CNI가 미확인이라 배포판별 설치 명령은 아직 제공하지 않습니다.

## 준비 순서 — 인프라 담당자·각 새 노드

1. 중복 없는 hostname·고정 IP, 라우팅·DNS·시간 동기화를 준비합니다.
2. OS·앱 데이터 디스크의 용량·권한·재부팅 후 마운트를 확인합니다.
3. 확정된 Kubernetes 버전에 맞게 swap·커널·sysctl·cgroup을 설정합니다.
4. 승인된 런타임·Kubernetes 도구·CNI와 필요한 이미지를 준비합니다.
5. 노드 런타임의 registry CA·인증·mirror와 이미지 접근을 확인합니다.

사내 서버의 인터넷 접근을 전제하지 않습니다. 패키지·이미지·고정 chart는 승인된 mirror 또는 반입 환경에서 준비하고 버전·아키텍처·checksum을 확인합니다.
chart 반입과 컨테이너 이미지 반입은 별도이며, Docker의 이미지가 Kubernetes 런타임에도 있다고 가정하지 않습니다.

## 필요한 통신

| 출발 → 도착 | 확인 내용 |
| --- | --- |
| 관리 PC·노드 → API VIP → Control Plane | API 포트·LB backend |
| Control Plane 상호 | 실제 etcd·제어면 구성에 필요한 통신 |
| Control Plane·Worker 상호 | kubelet·선택한 CNI의 포트·프로토콜 |
| 모든 노드 → DNS·시간 서버·registry·mirror | 이름 해석·CA·인증·접근 |
| 사용자 PC → APP VIP → Worker | 443 전달·상태 검사 |
| 앱 → DB·스토리지·OIDC | 앱별 연동 주소·포트·권한 |

포트·OS 설정은 확정된 설치 버전과 CNI 요구사항으로 결정합니다. 검증 환경에 운영 IP를 재사용하지 않습니다.

## 배포 도구 — CP1

Git·Bash·Make·Python 3.10+·kubectl·OpenSSL을 준비합니다.
Helm 앱은 각 앱의 README와 `helm/chart.lock.json`에 맞는 Helm·chart가 필요합니다.

```bash
git --version
bash --version
make --version
python3 --version
kubectl version --client -o yaml
openssl version
```

Helm을 쓴다면 `helm version --short`도 확인합니다. 이미지 빌드는 별도 환경에서 수행할 수 있습니다.

**완료 기준:** 네트워크·디스크·런타임·CRI·이미지 접근·필수 도구가 정상이며, 적용한 버전과 설치 명령이 기록되어 있습니다.
