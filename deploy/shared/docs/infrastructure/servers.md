# 서버·노드와 설치 기준

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

서버명·IP·역할·접속 정보·OS·설치 버전의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
**자료 대조일: 2026-11-05 / 담당자: 미확인.** 사용자 확인일과 실제 적용 여부는 각 항목의 근거를 따릅니다.

## 서버 목록

노드명·IP·역할과 당시 Ready는 **2026-09-16 사용자 확인**, Worker 용도 지정은 **2026-10-27 사용자 확인** 기록입니다.
근거는 Git의 `ca96e3dc:deploy/shared/docs/infrastructure/cluster.md`입니다.
CP1의 2026-10-30 추가 버전 확인은 [설치 기준](servers.md#확인된-worker-설치-기준)에 유지합니다.

| 역할·용도 | 서버·노드명 | 기록된 노드 IP | 근거·확인 상태 |
| --- | --- | --- | --- |
| CP1·배포 관리 명령 실행 | `khplane01w06` | `10.172.40.84` | control-plane, Kubernetes API·etcd. 2026-09-16 Ready 기록, 2026-10-30 CP1 추가 확인 |
| CP2 | `khplane01w07` | `10.172.40.86` | control-plane, Kubernetes API·etcd. 2026-09-16 Ready 기록 |
| CP3 | `khplane01w08` | `10.172.40.85` | control-plane, Kubernetes API·etcd. 2026-09-16 Ready 기록 |
| Keycloak 전용 Worker·기존 Traefik | `khplane01w09` | `10.172.40.87` | 2026-09-16 worker·Ready 기록. 2026-10-27 Keycloak 전용 Worker로 사용자 지정 |
| MinIO 배치 대상 Worker·APP VIP backend | `khplanew01` | `10.172.40.117` | 2026-09-16 worker·Ready 기록. 2026-10-27 MinIO·초기화 Job 배치 지정, 배포 성공 확인은 별도 |

기록된 클러스터는 제어면 3대·Worker 2대, etcd 3-node HA 구성입니다. 최신 Ready·추가 노드·Pod 배치는 다시 조회합니다.
SSH 포트·접속 계정·관리망에서의 접근 가능 여부는 미확인입니다. 위 노드 IP를 SSH 접속 성공 기록으로 간주하지 않습니다.

별도 서버 기록: `khinfow01`(`10.172.117.91`, 12 vCPU·72GiB·1TB)은 과거 Portal 통합 시험 예정 서버입니다.
2026-09-16 클러스터 5대 목록에는 포함되지 않았으며 `khplanew01`과 다른 서버입니다. 현재 사용 용도·접속 상태는 미확인입니다.

## 확인된 Worker 설치 기준

확인일은 **2026-10-30**, 근거는 사용자가 제공한 CP1의 버전 명령과 `kubectl get nodes -o wide` 결과입니다.
Worker의 OS도 CP1과 같다는 사용자 확인을 반영했습니다. 아래 값은 조회한 CP1 기준이며
다른 제어면·Worker·API server의 버전까지 일괄 검증한 결과는 아닙니다.

| 항목 | 확인값 | 근거 |
| --- | --- | --- |
| CP1 노드 | `khplane01w06`, `Ready`, `control-plane` | 노드 조회 |
| OS | Ubuntu 22.04.2 LTS (Jammy) | CP1 `/etc/os-release`, Worker는 동일 OS라는 사용자 확인 |
| CP1 아키텍처 | `x86_64` / amd64 | CP1 `uname -m` |
| kubeadm·kubelet | `v1.36.0` | CP1 버전 명령과 노드 조회 |
| containerd | `2.2.1` | CP1 버전 명령과 노드 조회 |
| CP1 커널 | `5.15.0-60-generic` | 노드 조회; 새 Worker 커널의 고정 설치값은 아님 |

[Worker 설치 절차](../kubernetes/03-worker.md#2-빈-서버에-프로그램-설치설정--새-worker)는
새 Ubuntu 22.04 amd64 서버에서 사내 패키지·이미지 미러로 Kubernetes 1.36.0과 containerd 2.2.1을 설치하도록 작성했습니다.
실제 Worker 아키텍처, CNI·MTU·통신 포트, 기존 cgroup 설정, 패키지·이미지 미러와 CA·인증,
사내 미러 접근 여부, 가입 endpoint와 API VIP의 관계는 인프라 담당자와 추가 확인합니다.
확인한 담당자 이름은 제공되지 않았습니다. 네트워크 주소는 실제 가입 명령과 운영 설정을 기준으로 사용합니다.

## 추가 확인·접속 정보

| 대상 | 확인할 정보 | 현재 상태 |
| --- | --- | --- |
| 클러스터 5대·별도 시험 서버 | SSH 포트·접속 계정 또는 발급 절차·관리망 경유지 | 미확인 |
| 노드별 자원 | CPU·메모리·디스크·마운트·각 노드의 커널·런타임 버전 | CP1·별도 시험 서버의 위 기록 외 미확인 |
| 실행 기반 | etcd 설치 방식·CRI socket·cgroup·노드 registry CA/인증 | 미확인. CP1 containerd 버전 확인과 별도로 실제 설정·인증서·권한 확인 필요 |
| 최신 구성 | 추가·교체·퇴역 서버와 최신 Ready·역할 | 최신 조회 필요. 기존 주소는 확인일과 함께 유지 |

## 조회와 관련 작업

[현재 환경 확인](../kubernetes/09-baseline.md)에서 노드·OS·버전을 조회합니다.
VIP·DNS는 [네트워크](network.md), 앱 배치는 [서비스](services.md#앱별-배치와-스토리지-선언), 파일 위치는 [운영 위치](operations.md)를 함께 확인합니다.
