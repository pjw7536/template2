# 서버·노드와 설치 기준

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

서버명·IP·역할·접속 정보·OS·설치 버전의 관리 원본입니다. 기록 형식은 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.

## 서버 목록

노드명·IP·역할은 사용자 확인값입니다. Ready·추가 노드·실제 Pod 배치는 작업 전 조회합니다.
OS·버전의 확인 범위는 [설치 기준](#확인된-worker-설치-기준)을 따릅니다.

| 역할·용도 | 서버·노드명 | 노드 IP | 구성·확인 상태 |
| --- | --- | --- | --- |
| CP1·배포 관리 명령 실행 | `khplane01w06` | `10.172.40.84` | control-plane, Kubernetes API·etcd |
| CP2 | `khplane01w07` | `10.172.40.86` | control-plane, Kubernetes API·etcd |
| CP3 | `khplane01w08` | `10.172.40.85` | control-plane, Kubernetes API·etcd |
| Keycloak 전용 Worker·공용 Traefik | `khplane01w09` | `10.172.40.87` | 사용자 지정 Worker 용도 |
| MinIO 배치 대상 Worker·APP VIP backend | `khplanew01` | `10.172.40.117` | MinIO·초기화 Job 배치 대상. 저장소 연결은 별도 조회 |
| Airflow·Monitoring 배치 대상 Worker | `khinfow01` | `10.172.117.91` | `khplanew01`과 다른 서버. 클러스터 Worker 추가는 사용자 확인. 12 vCPU·72GiB·1TB. 배포 대상은 `deploy/airflow/env/k8s.env`·`deploy/monitoring/env/k8s.env`의 `NODE_NAME=khinfow01` 선언 |

관리 대상 클러스터는 제어면 3대·Worker 3대, etcd 3-node HA 구성입니다.
위 노드 IP를 SSH 접속 성공 기록으로 간주하지 않습니다. SSH 포트·접속 계정·관리망 접근 가능 여부는 [추가 확인](#추가-확인접속-정보)에 있습니다.

### Portal Docker 환경

Portal 테스트와 운영은 서로 다른 서버에서 Docker 기반으로 실행했다는 사용자 확인이 있습니다.
접속 용도와 공개 주소는 [서비스 원본](services.md#portal-테스트운영-접속-구분)에서 관리하며, 아래 구분을 실제 OS hostname이나 Kubernetes 노드명으로 간주하지 않습니다.
두 환경을 현재 준비 중인 Kubernetes 클러스터로 옮기는 것은 사용자 확인 목표이며, 기존 Docker 서버를 Worker로 가입시키거나 폐기한다는 결정은 아닙니다.

| 역할·대상 | 서버 관계·실행 기반 | 확인 상태 | 남은 확인 |
| --- | --- | --- | --- |
| Portal 테스트 서버 | 운영과 별도 서버, Docker 기반 | 사용자 확인 | 실제 hostname·IP·OS·아키텍처·SSH·현재 가동 상태·담당자, 전환할 Worker·자원·스토리지와 적용 여부 |
| Portal 운영 서버 | 테스트와 별도 서버, Docker 기반 | 사용자 확인 | 실제 hostname·IP·OS·아키텍처·SSH·현재 가동 상태·담당자, 전환할 Worker·자원·스토리지와 적용 여부 |

## 확인된 Worker 설치 기준

사용자가 제공한 CP1의 버전 명령과 `kubectl get nodes -o wide` 결과가 근거입니다. Worker의 OS는 CP1과 같다는 사용자 확인값입니다.
아래 버전은 CP1 기준이며 다른 제어면·Worker·API server의 버전까지 일괄 검증한 결과는 아닙니다.

| 항목 | 확인값 | 근거 |
| --- | --- | --- |
| CP1 노드 | `khplane01w06`, `control-plane` | 노드 조회. 현재 Ready는 작업 전 재조회 |
| OS | Ubuntu 22.04.2 LTS (Jammy) | CP1 `/etc/os-release`, Worker는 동일 OS라는 사용자 확인 |
| CP1 아키텍처 | `x86_64` / amd64 | CP1 `uname -m` |
| kubeadm·kubelet | `v1.36.0` | CP1 버전 명령과 노드 조회 |
| containerd | `2.2.1` | CP1 버전 명령과 노드 조회 |
| CP1 Airflow 이미지 빌드 도구 | nerdctl·BuildKit으로 빌드 수행 | 사용자 확인. 설치 버전·실제 소켓·빌드 namespace·생성 이미지 존재 여부는 서버 조회 필요. 설정 기준은 [이미지 준비](../../../airflow/docs/02-artifacts.md#containerd-빌드-도구-준비) 참조 |
| CP1 커널 | `5.15.0-60-generic` | 노드 조회. 새 Worker 커널의 고정 설치값은 아님 |

[Worker 설치 절차](../kubernetes/worker.md#2-빈-서버에-프로그램-설치설정--새-worker)는 새 Ubuntu 22.04 amd64 서버에
사내 패키지·이미지 미러로 Kubernetes 1.36.0과 containerd 2.2.1을 설치합니다. 네트워크 주소는 실제 가입 명령과 운영 설정을 기준으로 사용합니다.

## 추가 확인·접속 정보

| 대상 | 확인할 정보 | 현재 상태 |
| --- | --- | --- |
| 클러스터 6대 | SSH 포트·접속 계정 또는 발급 절차·관리망 경유지·담당자 | 미확인 |
| 노드별 자원 | CPU·메모리·디스크·마운트·각 노드의 커널·런타임 버전 | CP1·`khinfow01`의 위 기록 외 미확인 |
| 노드 상태·배치 | `khplane01w09`·`khplanew01`·`khinfow01`의 Ready·접속 상태·실제 앱 Pod 배치 | 배포 전 조회 필요 |
| 실행 기반 | etcd 설치 방식·CRI socket·cgroup·노드 registry CA/인증 | 미확인. CP1 containerd 버전 확인과 별도로 실제 설정·인증서·권한 확인 필요 |
| Worker 설치 전제 | 실제 Worker 아키텍처, CNI·MTU·통신 포트, 기존 cgroup 설정, 패키지·이미지 미러와 CA·인증, 사내 미러 접근 여부, 가입 endpoint와 API VIP의 관계 | 인프라 담당자와 추가 확인. 담당자 미확인 |
| 최신 구성 | 추가·교체·퇴역 서버와 최신 Ready·역할 | 작업 전 노드 목록·주소·역할 대조 필요 |
| Kubernetes 버전 | API server·각 노드 kubelet의 실제 버전 | 충돌: CP1 확인값 `v1.36.0`, [metrics-server 안내](../kubernetes/control-plane.md#metrics-server-설치)의 기록 1.36.4. `kubectl version`·노드 조회로 확인 필요 |

## 조회와 관련 작업

[현재 환경 확인](../kubernetes/baseline.md)에서 노드·OS·버전을 조회합니다.
VIP·DNS는 [네트워크](network.md), 앱 배치는 [서비스](services.md#앱별-배치와-스토리지-선언), 파일 위치는 [운영 위치](operations.md)를 함께 확인합니다.
