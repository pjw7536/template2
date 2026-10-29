# 사내 배포 문서 안내

이 폴더는 사내 Kubernetes 배포에 필요한 앱별 설정과 운영 문서를 모아 둔 곳입니다.
사내 서버는 Kubernetes로만 배포하며, CI 검사에 쓰는 입력도 여기서 관리합니다.

외부 PC의 개발 환경은 [local/](../local/README.md)을 사용합니다. 개발용 env·mock·kind·실행 도구는 그곳에 있습니다.

```text
deploy/
├── README.md                 # 목적별 문서 색인
├── 01-SERVER_CHECKOUT.md        # 서버에 필요한 앱만 받는 공통 진입 안내
├── keycloak/                 # Keycloak 배포·OIDC·TLS와 배포 원본
├── minio/                    # 공용 객체 저장소·독립 설치
├── portal/                   # Portal 설정·운영 overlay·client 등록
├── airflow/                  # Airflow Helm 배포·이미지·백업
├── monitoring/               # kube-prometheus-stack Helm 배포
├── headlamp/                 # Kubernetes 조회 UI·권한·접속 도구
├── ftp/                      # 노드별 FTP 배포·스토리지
└── shared/
    ├── docs/
    │   ├── kubernetes/       # CP1~3 셋업·Traefik 셋업·Worker 추가
    │   ├── configuration/    # 앱 공통 환경설정·Secret 입력 규칙
    │   ├── operations/       # 서버 최초 기동·CP1 갱신 절차
    │   └── infrastructure/   # 클러스터·노드·VIP·DNS 현황
    ├── certs/                # 사이트별 인증서·공용 CA·추출과 적용 안내
    ├── ingress/              # 공용 Traefik 원본과 VIP 적용 절차
    └── scripts/              # 서버 기동·검사·체크아웃 도구
```

사내 서버는 [선택 체크아웃 안내](01-SERVER_CHECKOUT.md)를 따라 필요한 앱만 받습니다.
명령은 별도 안내가 없으면 저장소 루트에서 실행합니다.
기존 Kubernetes에서 Portal 외 서비스를 먼저 운영하려면 `platform`을 선택합니다.
서버에는 `deploy`와 루트 실행 파일을 받으며 `apps/`·`local/`·루트 `docs/`는 필요하지 않습니다.
공통 운영 문서는 `deploy/shared/docs`에 포함됩니다.
Portal을 추가할 때는 `all`로 확장하고 앱별 입력·migration·라우팅 연결을 수행합니다.

설정은 각 앱의 env 파일에서 관리합니다. 일반 설정과 비밀번호·토큰을 같은 파일에 넣고,
비공개 Git 저장소에서 변경 이력을 관리합니다. 검사와 배포 도구는 지정한 env 파일 하나를 읽습니다.

인증서·개인키 파일은 Git에 넣지 않고 서버에 별도로 준비합니다.

## 처음 읽는 순서

현재 배포 정의와 앱별 입력을 검사한 뒤 대상 클러스터의 상태를 조회합니다.
파일 검사 통과와 실제 서버 설치·로그인 성공은 구분합니다.

공통 인프라는 **세 가지 작업**으로 정리합니다.

| 작업 | 시작 문서 |
| --- | --- |
| CP1~3 셋업 | [제어면 3대 준비·구성·확인](shared/docs/kubernetes/01-control-plane.md) |
| Traefik 셋업 | [공용 HTTPS 진입점·TLS·VIP](shared/docs/kubernetes/02-traefik.md) |
| Worker 추가 | [빈 서버 준비·클러스터 가입·Ready 확인](shared/docs/kubernetes/03-worker.md) |

새 클러스터는 CP1~3 → Worker 최소 1대 → Traefik 순서로 준비합니다.
기존 클러스터에 Airflow용 서버만 추가한다면 Worker 추가 문서부터 진행합니다.
OS·설치 버전은 실제 서버 기준으로 확인하며 [전체 안내](shared/docs/kubernetes/README.md)에서 참고 문서를 찾을 수 있습니다.

기존 클러스터에 배포할 때는 다음 순서로 읽습니다.

1. [클러스터 구성](shared/docs/infrastructure/cluster.md)에서 배포 원본을 찾고 대상 노드·VIP를 조회합니다.
2. [선택 체크아웃](01-SERVER_CHECKOUT.md)에서 `platform`으로 Portal 외 서비스를 받습니다.
3. [환경설정](shared/docs/configuration/environment.md)에서 설정 소유권과 입력 위치를 확인합니다.
4. [앱별 배포 순서](shared/docs/kubernetes/05-applications.md)와 아래 앱 문서를 따라 검사·배포·접속 확인을 진행합니다.

앱별 실행 순서는 [서버 기동](shared/docs/operations/01-server-start.md),
APP VIP의 인증서와 접속 확인은 [VIP 절차](shared/ingress/01-VIP.md)를 참고합니다.

## 공통 준비와 운영

| 카테고리 | 문서 | 목적·사용 시점 |
| --- | --- | --- |
| 인프라 셋업 | [Kubernetes 가이드](shared/docs/kubernetes/README.md) | CP1~3 셋업·Traefik 셋업·Worker 추가 중 작업 선택 |
| 저장소 준비 | [선택 체크아웃](01-SERVER_CHECKOUT.md) | 처음 clone하거나 서버가 관리하는 앱 범위를 바꿀 때 |
| 인증서 | [사이트별 인증서 관리](shared/certs/README.md) | PFX/P7B 추출·검증·TLS Secret 갱신 |
| 설정 참고 | [환경설정](shared/docs/configuration/environment.md) | 앱별 env 위치·필수값 검사·Secret 등록 규칙을 확인할 때 |
| 운영 절차 | [서버 기동](shared/docs/operations/01-server-start.md) | 공용 기반 준비 후 앱별 검사·기동·확인 |
| 운영 절차 | [CP1 운영](shared/docs/operations/02-cp1.md) | 공통 Git·파일 관리와 앱별 반영 안내 |
| 인프라 현황 | [클러스터 현황](shared/docs/infrastructure/cluster.md) | 배포 원본·노드 배치·현재 상태 확인 방법을 찾을 때 |
| 인프라 구성 | [Traefik 셋업](shared/docs/kubernetes/02-traefik.md) | 공용 진입점 설치·TLS·VIP 접속 확인, 상세 원본은 [Ingress 참고](shared/ingress/README.md) |
| 인프라 적용 | [APP VIP 실행](shared/ingress/01-VIP.md) | 두 Worker의 443 연결·인증서 준비·서버 적용과 접속 검증 |

## 앱별 배포와 상세 작업

| 앱 | 시작 문서 | 상세 작업 |
| --- | --- | --- |
| Keycloak | [서버 배포·사내 OIDC·사용자 claim](keycloak/README.md) | [TLS 인증서·Secret 운영](keycloak/03_TLS.md) |
| Portal | [환경설정·배포 입력 순서](portal/README.md) | [운영 overlay·배포 순서](portal/k8s/overlays/prod/README.md), [Keycloak client 등록](portal/k8s/jobs/keycloak-client/README.md), [공용 MinIO](minio/README.md) |
| Airflow | [Helm 배포·이미지·스토리지](airflow/README.md) | 같은 문서에서 백업·데이터 이전·업데이트 안내 |
| Monitoring | [Kubernetes 모니터링](monitoring/README.md) | kube-prometheus-stack·Grafana·지표 저장 |
| Headlamp | [Kubernetes 운영 UI](headlamp/README.md) | Keycloak 로그인·그룹별 조회 권한·HTTPS 접속 |
| FTP | [서버별 FTP 배포](ftp/README.md) | 선택 노드의 로컬 저장소·직접 접속 |

## 문서를 추가하거나 수정할 때

- 여러 앱이 공유하는 설정 규칙·운영 절차·인프라 현황은 `shared/docs/`의 해당 카테고리에 둡니다. 이 경로는 모든 서버 선택 체크아웃에 포함됩니다.
- 입문 설명과 단계별 완료 기준은 `shared/docs/kubernetes/`에서 연결하고 앱별 실행 명령의 원본은 해당 앱 문서에 유지합니다.
- 앱별 시작점은 `<app>/README.md`, 특정 Job·overlay·Ingress의 사용법은 해당 원본 옆에 둡니다.
- 현재 배포 구성은 원본·env와 대조하고 앱별 안내에서 연결합니다. 실제 노드·서비스 상태는 대상 클러스터에서 조회합니다.
- 새 문서는 이 색인에 등록하고 상위 안내 링크를 제공합니다. 이동 시 현재 안내 문서의 상대 링크도 갱신합니다.

## 검사와 실행

```bash
# 선택한 서버 앱의 파일을 검사하며 local/이나 다른 앱은 필요하지 않습니다.
make server-check APP=keycloak

# Portal 외 서비스의 Helm·chart를 준비한 뒤 그룹 전체를 검사합니다.
make server-check APP=platform

# 기존 클러스터에서 공용 Ingress를 먼저 검사·적용합니다.
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"

# Keycloak 전달용 YAML 두 개를 생성합니다.
make k8s-export
```

`server-check`는 Keycloak·Portal·Airflow·FTP·Monitoring·Headlamp·MinIO의 prod Kubernetes 원본을 검사합니다.
Airflow는 먼저 [전용 안내](airflow/README.md)에 따라 Helm과 고정 chart를 준비해야 합니다.
Monitoring도 [전용 안내](monitoring/README.md)에 따라 Helm과 고정 chart를 준비한 뒤 검사합니다.
Headlamp도 [전용 안내](headlamp/README.md)에 따라 고정 chart를 준비한 뒤 검사합니다.
서버 검사는 `PROFILE=prod`를 사용합니다. 실제 입력은 `make env-check` 또는 외부 env를 받는
`deploy/shared/scripts/check-env.sh`로 별도 검사합니다.

외부 PC에서는 `make dev`, `make k8s-up`을 사용합니다.
`make k8s-render`는 로컬·서버 전체, `make k8s-render-local`은 로컬,
`make k8s-render-server`는 Keycloak·Portal 서버 전체 원본을 렌더링합니다.
선택 체크아웃에서는 앱별 `server-check`를 사용합니다.

## 소유권

- Keycloak 관리자·전용 DB·사내 OIDC 입력은 Keycloak, Portal client 입력은 Portal이 소유합니다.
- 앱 소스는 `apps/<app>`, 배포 정의는 `deploy/<app>`에서 관리합니다. local 개발 환경도 이 배포 정의를 참조합니다.
- 서버에는 기본적으로 배포 파일만 받습니다. 이미지를 빌드할 때만 `--with-source`로 앱 소스를 추가합니다.
- `platform`은 Portal을 제외한 서비스, `all`은 Portal을 포함한 서비스 파일을 선택합니다. checkout은 이전 범위를 교체합니다.
- 서버 검사·렌더링·배포는 local 없이 수행할 수 있어야 합니다.
- CI의 test 입력은 로컬 전용이 아니므로 `deploy/portal/env/test/`에 유지합니다.
- 실제 CP1 설정은 `/appdata/etchax-config/<app>/`에서 관리하고 외부 env 인자로 전달합니다.
- 생성 YAML은 원본에서 다시 생성하며 직접 수정하지 않습니다.
- 보조 Compose 상대 경로는 파일 기준입니다. 로컬 DB·API 검사는 local/shared/compose, CI API 검사는 portal/compose가 소유합니다.

서버 배포에는 Compose를 사용하지 않습니다. `portal/compose/test.yml`은 독립 CI API 검사에 사용합니다.
