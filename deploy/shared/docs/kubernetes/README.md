# Kubernetes 배포·운영 안내

[배포 문서 홈](../../../README.md) · [서버 현황 원본](../infrastructure/cluster.md)

현재 클러스터는 이미 구성되어 있습니다. **기존 서버에서는 현황 확인 → 앱 준비 → 배포 → 접속 검증 순서로 진행합니다.**

## 현재 서버 상황

아래는 저장소에 남은 확인 기록입니다. 실시간 서버 조회 결과가 아니므로 배포 전에 다시 확인합니다.

| 역할 | 노드 | IP | 상태 |
| --- | --- | --- | --- |
| CP1 | `khplane01w06` | `10.172.40.84` | Ready |
| CP2 | `khplane01w07` | `10.172.40.86` | Ready |
| CP3 | `khplane01w08` | `10.172.40.85` | Ready |
| Worker | `khplane01w09` | `10.172.40.87` | Ready |
| Worker | `khplanew01` | `10.172.40.117` | Ready |

노드명·IP·역할·Ready는 **2026-09-16 사용자 확인** 기준입니다.
CP는 클러스터를 관리하고 Worker는 앱을 실행합니다. OS·Kubernetes 버전·설치 도구·CNI·노드 사양은 미확인입니다.

| 접속·앱 | 기록된 상태 | 남은 확인 |
| --- | --- | --- |
| Kubernetes API | 기존 endpoint `10.172.26.148:6443`, etcd 3-node HA 기록 | 실제 LB·etcd 상태 |
| 업무 접속 | `etch.samsungds.net` → APP VIP `10.172.26.150:443` | TLS·실제 HTTPS 응답 |
| APP VIP backend | `10.172.40.117:443`, `10.172.40.87:443` 연결 확인 | 양쪽 Traefik 배치·응답, LB 상태 검사 |
| Keycloak | `khplane01w09`에서 운영 중이라는 보고, `https://etch-sso.samsungds.net` | 최신 Pod·인증서·사내 로그인, DNS의 VIP 전환 여부 |
| Airflow | 배포 코드 준비, 목표 URL `https://etch.samsungds.net/airflow` | 실제 배포·기동 여부 |
| 스토리지 | 2026-09-08에는 StorageClass 없음 | 현재 PV/PVC·공급 방식·백업 |

VIP·업무 DNS는 **2026-09-15 기록**, Keycloak 구동 확인은 **2026-09-10 사용자 보고**입니다.
현재 목표는 기존 Keycloak을 유지하면서 두 Worker의 공용 접속 경로를 확인하고 Airflow를 기동하는 것입니다.
Portal·Monitoring·Headlamp·FTP의 현재 기동 여부는 이 기록으로 확인할 수 없습니다.
과거 Portal 예정 서버 `khinfow01`은 현재 5대 목록에 없으며 `khplanew01`과 다른 서버입니다.

## 어디부터 읽나요?

| 상황 | 읽는 순서 |
| --- | --- |
| Kubernetes가 처음 | [00 용어와 구조](00-concepts.md) → 아래 기존 서버 순서 |
| 현재 서버에 앱 배포 | [01 현황 확인](01-baseline.md) → [04 준비](04-prerequisites.md) → [05 배포](05-applications.md) → [06 검증](06-verification.md) |
| 새 서버·검증 환경 구축 | [01 설치 기준 확인](01-baseline.md) → [02 서버 준비](02-servers.md) → [03 클러스터 구축](03-cluster.md) |
| 업데이트·장애 대응 | [07 운영과 문제 해결](07-operations.md) |

02~03장은 설치 기준이 확정되기 전의 준비 안내입니다. 빈 서버 설치 명령은 아직 완성되지 않았습니다.

## 명령 실행 위치

- **CP1:** 배포 계정으로 실행합니다. `make`·Git 명령은 checkout 루트에서 실행합니다.
- **Worker:** 해당 서버에 SSH로 접속해 디스크·데이터 폴더를 준비합니다.
- **내 PC:** SSH와 브라우저 접속을 확인합니다. VIP는 SSH 접속 대상이 아닙니다.

`read`에는 실제 값을 입력합니다. 새 터미널에서는 context와 변수를 다시 지정합니다.
상세 설정은 앱 문서, 서버 현황의 원본은 [cluster.md](../infrastructure/cluster.md)에서 관리하며 이 요약도 함께 맞춥니다.
