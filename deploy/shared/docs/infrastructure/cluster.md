# 사내 운영 클러스터 현황

[배포 문서 안내](../../../README.md) · [입문 가이드](../kubernetes/README.md) · [설치 기준 조회](../kubernetes/01-baseline.md)

> 노드 현황 기준일: 2026-09-16 사용자 확인 / APP VIP·DNS 기록: 2026-09-15
>
> 이 문서를 사내 Kubernetes topology와 workload 배치의 기준 정보로 사용합니다. 실제
> 배포 전에는 `kubectl get nodes -o wide` 결과와 비교해 상태 변경 여부를 확인합니다.
> 아래 5대의 노드명·역할·IP·Ready는 사용자가 제공한 현재 구성입니다. 에이전트가 서버를 조회한 결과는 아닙니다.
> 노드 확인은 VIP·DNS·앱 배포 성공을 의미하지 않으며 해당 항목은 각 기록의 확인 시점을 유지합니다.

```text
                  Kubernetes API VIP
                  10.172.26.148:6443
                           |
          ---------------------------------
          |               |               |
         CP1             CP2             CP3
   khplane01w06     khplane01w07     khplane01w08
    10.172.40.84     10.172.40.86     10.172.40.85
          |               |               |
          +---------------+---------------+
                          |
                   etcd 3-node HA
                          |
             -------------------------
             |                       |
            Worker                 Worker
        khplane01w09             khplanew01
        10.172.40.87           10.172.40.117
```

| Node | IP | Role | CPU | Memory | Disk | Workload / Status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `khplane01w06` | `10.172.40.84` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w07` | `10.172.40.86` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w08` | `10.172.40.85` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w09` | `10.172.40.87` | worker | 미확인 | 미확인 | 미확인 | Keycloak, PostgreSQL, Traefik / Ready |
| `khplanew01` | `10.172.40.117` | worker | 미확인 | 미확인 | 미확인 | APP VIP Backend 등록 기록 있음 / Ready |

위 표의 workload는 기존 배치 기록이며 2026-09-16 확인 범위는 노드 상태까지입니다.

### 과거 계획과 현재 목록의 구분

`khinfow01`(`10.172.117.91`, 12 vCPU·72GiB·1TB)은 과거 Portal 통합 시험 예정 서버입니다.
2026-09-16 제공된 현재 클러스터 목록에는 없어 위 현황에서 제외했습니다.
`khplanew01`의 별칭으로 취급하거나 과거 사양을 현재 Worker에 대입하지 않습니다.

## APP VIP·DNS·배포 현황 — 2026-09-15

| 항목 | 값 / 상태 | 확인 근거 |
| --- | --- | --- |
| CP VIP | `10.172.26.148:6443` | 기존 Kubernetes API 기록 |
| APP VIP | `10.172.26.150:443` | 사용자 확인: 인프라팀 발급, SSH 접근 불가 |
| 업무 DNS | `etch.samsungds.net` → `10.172.26.150` | 사용자 확인: DNS 설정 완료 |
| APP VIP Backend 1 | `10.172.40.117:443` | 2026-09-15 LB 연결 확인; 2026-09-16 Node `khplanew01` Ready 확인 |
| APP VIP Backend 2 | `10.172.40.87:443` | 2026-09-15 LB 연결 확인; 2026-09-16 Node `khplane01w09` Ready 확인 |
| Keycloak DNS | `etch-sso.samsungds.net` | 마지막 공유 상태는 Worker 직결, APP VIP로 변경 완료 여부 미확인 |
| Keycloak 구동 | 기존 운영 중 | 사용자 보고, 최신 Pod 상태는 미조회 |
| Traefik 두 Worker 배치 | 프로젝트 코드 준비 완료 | 실제 서버 적용·두 Backend 응답 여부 미확인 |
| Airflow | 배포 코드 준비, 목표 URL `https://etch.samsungds.net/airflow` | 실제 배포·기동 여부 미확인 |
| 업무 도메인 TLS | `etch.samsungds.net`을 포함하는 인증서 필요 | 발급·Kubernetes Secret 등록 여부 미확인 |
| LB 동작 | TCP 전달·Traefik TLS 종료를 적용할 계획 | 실제 TLS offloading·Health Check 설정값 미확인 |

현재 `10.172.40.117`의 Kubernetes 노드명은 `khplanew01`로 확인됐습니다.
노드 등록과 Traefik의 해당 Worker 배치·HTTPS 응답은 별도로 검증합니다.

```text
etch.samsungds.net → APP VIP 10.172.26.150:443
                          ├─ 10.172.40.117:443 → Traefik 배치 준비
                          └─ 10.172.40.87:443  → 기존 Traefik 확장 준비
                                                     │
                                                     └─ /airflow → Airflow 배포 준비
```

VIP 연결은 인프라팀에서 설정했으며, 위 앱 라우팅은 저장소의 배포 계획입니다.
현재 목표는 기존 Keycloak 유지와 Airflow 기동입니다. 두 Worker에 Traefik을 배치하더라도
앱·DB를 복제하는 것은 아닙니다. 서버 적용과 확인은 [APP VIP 실행 절차](../../ingress/VIP.md)를 따릅니다.

## 확정된 클러스터·Keycloak 정보

- Kubernetes API endpoint: `10.172.26.148:6443`
- Control Plane: 3개 노드, etcd 3-node HA
- Keycloak namespace: `etch-sso`
- Keycloak 공개 DNS: `etch-sso.samsungds.net`
- Keycloak 접속 URL: `https://etch-sso.samsungds.net`
- Keycloak worker: `khplane01w09`(`10.172.40.87`)
- Keycloak workload: Keycloak, 전용 PostgreSQL, 기존 Traefik (공용 진입점으로 확장하는 코드 준비 완료)
- Keycloak PostgreSQL local PV: `/appdata/keycloak-postgres`, 50Gi
- Keycloak 구동: 2026-09-10 사용자 확인 완료
- Keycloak Ingress: `traefik` IngressClass, 기존 `keycloak-tls` Secret 사용
- StorageClass: 2026-09-08 확인 시 없음, Portal 배포 전 재확인 필요
- Kubernetes version과 CNI: 문서 기준 미확인
- Keycloak TLS 인증서의 브라우저 신뢰와 full chain: 최종 확인 필요
- Keycloak을 통한 사내 OIDC 실제 로그인: 최종 확인 필요

## 빈 서버 재현에 필요한 설치 기준

| 항목 | 현재 기록 | 다음 확인 |
| --- | --- | --- |
| 노드 이름·IP·역할·Ready | 2026-09-16 사용자 확인, 위 5대 | 배포 전 nodes 조회 |
| OS·커널·노드 사양 | 미확인 | 각 노드 OS·디스크·자원 조회 |
| Kubernetes 설치 도구·버전 | 미확인 | version 조회와 인프라 구축 기록 |
| 런타임·CRI·cgroup | 미확인 | 노드 서비스·설정 확인 |
| CNI·Pod/Service CIDR·MTU | 미확인 | 시스템 Pod·설치 원본과 관리자 확인 |
| API VIP·etcd 구성 | API VIP·etcd 3-node HA 기존 기록 | 실제 LB·etcd 설치 방식·상태 재확인 |
| StorageClass·앱 PV·백업 | 과거 기록만 있음 | storageclass·pv·pvc와 Worker 마운트 조회 |

[환경 조회와 기록 양식](../kubernetes/01-baseline.md)을 사용해 확인값·확인일·근거를 갱신합니다.
앱 chart가 요구하는 최소 Kubernetes 버전을 현재 설치 버전 또는 새 서버 권장 버전으로 기록하지 않습니다.

## 2026-09-22 인증서·Headlamp 후속 기록

- 사용자가 Keycloak·업무 도메인의 PFX/P7B, 추출한 fullchain·개인키, SECDS-T2 루트·중간 CA 보유를 확인했습니다.
- 보관 위치는 `deploy/shared/certs/`의 사이트별 폴더입니다. [추출·적용 안내](../../certs/README.md)를 따릅니다.
- Headlamp의 운영 도메인·issuer·그룹 조회 권한 구성은 저장소에 반영되어 있습니다. 실제 서버의 Secret·로그인·제어면 OIDC 상태는 미조회입니다.
