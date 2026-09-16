# 사내 운영 클러스터 현황

[배포 문서 안내](../../../README.md)

> 노드 현황 기준일: 2026-09-10 / APP VIP·DNS 추가 기록: 2026-09-15
>
> 이 문서를 사내 Kubernetes topology와 workload 배치의 기준 정보로 사용합니다. 실제
> 배포 전에는 `kubectl get nodes -o wide` 결과와 비교해 상태 변경 여부를 확인합니다.
> 아래 기존 노드의 Ready 표시는 2026-09-10 기록입니다. 2026-09-15에는 외부 PC에 사내
> kubeconfig가 없어 실시간 상태를 조회하지 못했으며, VIP·DNS 값은 사용자 확인 내용입니다.

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
        Keycloak worker       Portal worker 예정
        khplane01w09             khinfow01
        10.172.40.87          10.172.117.91
```

| Node | IP | Role | CPU | Memory | Disk | Workload / Status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `khplane01w06` | `10.172.40.84` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w07` | `10.172.40.86` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w08` | `10.172.40.85` | control-plane | 미확인 | 미확인 | 미확인 | Kubernetes API, etcd / Ready |
| `khplane01w09` | `10.172.40.87` | worker | 미확인 | 미확인 | 미확인 | Keycloak, PostgreSQL, Traefik / Ready |
| 노드명 미확인 | `10.172.40.117` | APP VIP Backend worker | 미확인 | 미확인 | 미확인 | 인프라팀 LB에 443 등록 / Kubernetes Node 매핑·Ready 미확인 |
| `khinfow01` | `10.172.117.91` | worker | 12 vCPU | 72GiB | 1TB | Portal 전체 테스트 예정 / Kubernetes Ready 상태 미확인 |

## APP VIP·DNS·배포 현황 — 2026-09-15

| 항목 | 값 / 상태 | 확인 근거 |
| --- | --- | --- |
| CP VIP | `10.172.26.148:6443` | 기존 Kubernetes API 기록 |
| APP VIP | `10.172.26.150:443` | 사용자 확인: 인프라팀 발급, SSH 접근 불가 |
| 업무 DNS | `etch.samsungds.net` → `10.172.26.150` | 사용자 확인: DNS 설정 완료 |
| APP VIP Backend 1 | `10.172.40.117:443` | 사용자 확인: 인프라팀 연결 완료 |
| APP VIP Backend 2 | `10.172.40.87:443` | 사용자 확인: 인프라팀 연결 완료 |
| Keycloak DNS | `etch-sso.samsungds.net` | 마지막 공유 상태는 Worker 직결, APP VIP로 변경 완료 여부 미확인 |
| Keycloak 구동 | 기존 운영 중 | 사용자 보고, 최신 Pod 상태는 미조회 |
| Traefik 두 Worker 배치 | 프로젝트 코드 준비 완료 | 실제 서버 적용·두 Backend 응답 여부 미확인 |
| Airflow | 배포 코드 준비, 목표 URL `https://etch.samsungds.net/airflow` | 실제 배포·기동 여부 미확인 |
| 업무 도메인 TLS | `etch.samsungds.net`을 포함하는 인증서 필요 | 발급·Kubernetes Secret 등록 여부 미확인 |
| LB 동작 | TCP 전달·Traefik TLS 종료를 적용할 계획 | 실제 TLS offloading·Health Check 설정값 미확인 |

`10.172.40.117`과 기존 Portal 예정 서버 `10.172.117.91`은 서로 다른 IP입니다.
동일 서버의 다른 인터페이스인지도 확인되지 않았으므로 노드 이름·사양을 서로 대입하지 않습니다.

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
