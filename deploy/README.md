# 사내 배포 문서 안내

사내 서버는 Kubernetes로만 배포합니다. 앱별 Kubernetes 원본과 CI 입력을 관리합니다.
외부 PC 전용 env·mock·kind·개발 실행 도구는 [local/](../local/README.md)에 있습니다.

```text
deploy/
├── README.md                 # 목적별 문서 색인
├── SERVER_CHECKOUT.md        # 서버에 필요한 앱만 받는 공통 진입 안내
├── keycloak/                 # Keycloak 배포·OIDC·TLS와 배포 원본
├── portal/                   # Portal 설정·운영 overlay·client 등록
├── airflow/                  # Airflow Helm 배포·이미지·백업
├── monitoring/               # kube-prometheus-stack Helm 배포
└── shared/
    ├── docs/
    │   ├── configuration/    # 앱 공통 환경설정·Secret 입력 규칙
    │   ├── operations/       # 서버 최초 기동·CP1 갱신 절차
    │   └── infrastructure/   # 클러스터·노드·VIP·DNS 현황
    ├── ingress/              # 공용 Traefik 원본과 VIP 적용 절차
    └── scripts/              # 서버 기동·검사·체크아웃 도구
```

사내 서버는 [선택 체크아웃 안내](SERVER_CHECKOUT.md)를 따라 필요한 앱만 받습니다.
명령은 별도 안내가 없으면 저장소 루트에서 실행합니다.

## 처음 읽는 순서

1. [클러스터 현황](shared/docs/infrastructure/cluster.md)에서 대상 노드·VIP와 확인 시점을 확인합니다.
2. [선택 체크아웃](SERVER_CHECKOUT.md)으로 필요한 앱을 받습니다.
3. [환경설정](shared/docs/configuration/environment.md)에서 설정 소유권과 입력 위치를 확인합니다.
4. 기존 Keycloak에 Airflow를 연결하려면 [서버 최초 준비](shared/docs/operations/server-start.md)를 수행한 뒤, APP VIP 환경의 [VIP 적용 절차](shared/ingress/VIP.md)를 따릅니다. 앱별 배포는 아래 전용 문서에서 시작합니다.

## 공통 준비와 운영

| 카테고리 | 문서 | 목적·사용 시점 |
| --- | --- | --- |
| 저장소 준비 | [선택 체크아웃](SERVER_CHECKOUT.md) | 처음 clone하거나 서버가 관리하는 앱 범위를 바꿀 때 |
| 설정 참고 | [환경설정](shared/docs/configuration/environment.md) | 앱별 env 위치·필수값 검사·Secret 등록 규칙을 확인할 때 |
| 운영 절차 | [서버 기동](shared/docs/operations/server-start.md) | 기존 Keycloak과 Airflow의 최초 준비·기동·재적용 |
| 운영 절차 | [CP1 운영](shared/docs/operations/cp1.md) | CP1 파일 배치·외부 설정 보관·Keycloak 단독 배포와 pull 이후 반영 |
| 인프라 현황 | [클러스터 현황](shared/docs/infrastructure/cluster.md) | 노드·VIP·DNS·배치 계획과 확인된 상태를 조회할 때 |
| 인프라 구성 | [공용 Ingress](shared/ingress/README.md) | Traefik 원본 소유권·namespace 감시·앱별 연결 원리 |
| 인프라 적용 | [APP VIP 실행](shared/ingress/VIP.md) | 두 Worker의 443 연결·인증서 준비·서버 적용과 접속 검증 |

## 앱별 배포와 상세 작업

| 앱 | 시작 문서 | 상세 작업 |
| --- | --- | --- |
| Keycloak | [서버 배포·사내 OIDC·사용자 claim](keycloak/README.md) | [TLS 인증서·Secret 운영](keycloak/TLS.md) |
| Portal | [환경설정·배포 입력 순서](portal/README.md) | [운영 overlay·배포 순서](portal/k8s/overlays/prod/README.md), [Keycloak client 등록](portal/k8s/jobs/keycloak-client/README.md) |
| Airflow | [Helm 배포·이미지·스토리지](airflow/README.md) | 같은 문서에서 백업·데이터 이전·업데이트 안내 |
| Monitoring | [Kubernetes 모니터링](monitoring/README.md) | kube-prometheus-stack·Grafana·지표 저장 |
| Headlamp | [Kubernetes 운영 UI](headlamp/README.md) | 조회용 토큰 로그인·localhost 접속 |
| FTP | [서버별 FTP 배포](ftp/README.md) | 선택 노드의 로컬 저장소·직접 접속 |

## 문서를 추가하거나 수정할 때

- 여러 앱이 공유하는 설정 규칙·운영 절차·인프라 현황은 `shared/docs/`의 해당 카테고리에 둡니다. 이 경로는 모든 서버 선택 체크아웃에 포함됩니다.
- 앱별 시작점은 `<app>/README.md`, 특정 Job·overlay·Ingress의 사용법은 해당 원본 옆에 둡니다.
- 공통 현황은 한 문서에서 관리하고 앱별 안내에서는 링크로 참조합니다. 현황을 갱신할 때 확인일과 미확인 항목도 함께 기록합니다.
- 새 문서는 이 색인에 등록하고 상위 안내 링크를 제공합니다. 이동 시 현재 안내 문서의 상대 링크도 갱신합니다.

## 검사와 실행

```bash
# 선택한 서버 앱의 파일을 검사하며 local/이나 다른 앱은 필요하지 않습니다.
make server-check APP=keycloak

# Keycloak 전달용 YAML 두 개를 생성합니다.
make k8s-export
```

`server-check`는 Keycloak·Portal·Airflow·FTP·Monitoring·Headlamp의 prod Kubernetes 원본을 검사합니다.
Airflow는 먼저 [전용 안내](airflow/README.md)에 따라 Helm과 고정 chart를 준비해야 합니다.
Monitoring도 [전용 안내](monitoring/README.md)에 따라 Helm과 고정 chart를 준비한 뒤 검사합니다.
Headlamp도 [전용 안내](headlamp/README.md)에 따라 고정 chart를 준비한 뒤 검사합니다.
과거 oidc 환경 전용 Kubernetes 정의도 없으므로 PROFILE=oidc는 지원하지 않습니다. 실제 입력은 `make env-check` 또는 외부 env를 받는
`deploy/shared/scripts/check-env.sh`로 별도 검사합니다.

외부 PC에서는 `make dev`, `make k8s-up`을 사용합니다.
`make k8s-render`는 로컬·서버 전체, `make k8s-render-local`은 로컬,
`make k8s-render-server`는 Keycloak·Portal 서버 전체 원본을 렌더링합니다.
선택 체크아웃에서는 앱별 `server-check`를 사용합니다.

## 소유권

- Keycloak 관리자·전용 DB·사내 OIDC 입력은 Keycloak, Portal client 입력은 Portal이 소유합니다.
- 실제 앱 소스는 `apps/<app>`, 공통 배포 정의는 `deploy/<app>`에 원본을 하나만 유지합니다. 기본 서버 checkout은 배포 전용이며 빌드는 `--with-source`로 소스를 추가합니다. local이 공통 정의를 참조합니다.
- 서버 검사·렌더링·배포는 local 없이 수행할 수 있어야 합니다.
- CI의 test 입력은 로컬 전용이 아니므로 `deploy/portal/env/test/`에 유지합니다.
- 실제 CP1 설정은 `/appdata/etchax-config/<app>/`에서 관리하고 외부 env 인자로 전달합니다.
- 생성 YAML은 원본에서 다시 생성하며 직접 수정하지 않습니다.
- Compose 상대 경로는 파일 기준입니다. 소스·데이터 기본 경로는 이전 위치를 유지합니다.
- 과거 ExecPlan은 당시 경로를 기록하므로 현재 명령은 이 안내를 기준으로 사용합니다.

서버 배포에는 Compose를 사용하지 않습니다. `portal/compose/test.yml`은 독립 CI API 검사에 사용합니다.
