# 서버 배포 안내

이 폴더는 사내 Kubernetes의 공통 기반과 앱별 설치·운영을 관리합니다.
처음 맡은 운영자는 아래 작업 선택에서 시작하고, 해당 절차의 완료 기준을 확인한 뒤 다음 단계로 진행합니다.
명령은 별도 안내가 없으면 **관리 호스트의 저장소 루트**에서 실행합니다.

## 처음 읽는 순서

| 현재 상황 | 읽는 순서 |
| --- | --- |
| 환경과 접속 대상을 파악해야 함 | [사내 인프라 정보](shared/docs/infrastructure/README.md) → 필요한 주제의 원본 → [실제 환경 조회](shared/docs/kubernetes/baseline.md) |
| 서버에 배포 파일을 처음 받음 | [선택 checkout](shared/docs/operations/checkout.md) → [환경설정 규칙](shared/docs/configuration/environment.md) → 해당 앱 README |
| 새 클러스터를 구성함 | [CP1~3 준비](shared/docs/kubernetes/control-plane.md) → [Worker 최소 1대 추가](shared/docs/kubernetes/worker.md) → [Traefik 준비](shared/docs/ingress/setup.md) |
| 기존 클러스터에 앱을 설치함 | [배포 준비](shared/docs/operations/prepare.md) → [앱 의존 관계와 설치 순서](shared/docs/operations/applications.md) → 해당 앱 README |
| 설정·이미지를 갱신하거나 장애에 대응함 | [서버 운영 흐름](shared/docs/operations/README.md) → 해당 앱의 운영 문서 |

사내 서버·주소·미러·데이터 위치는 **저장소 선언과 실제 적용 상태를 구분**해 확인합니다.
파일 검사·렌더 통과 후에도 실제 rollout·HTTPS·로그인·업무 기능을 확인해야 합니다.
클러스터 상태·접속·담당자가 불확실하면 [인프라 원본](shared/docs/infrastructure/README.md)에 남은 확인을 기록합니다.

## 앱별 배포와 상세 작업

각 앱 README는 준비 → 설정 → 배포 → 검증 순서와 운영 문서를 안내합니다.

| 앱 | 시작 문서 | 먼저 준비할 것·주요 확인 |
| --- | --- | --- |
| Keycloak | [인증 서버](keycloak/README.md) | 전용 DB·Worker·TLS, 사내 로그인·사용자 claim |
| MinIO | [공용 객체 저장소](minio/README.md) | Worker 저장소 또는 StorageClass, 공용 Traefik·버킷·계정 |
| Airflow | [워크플로 실행](airflow/README.md) | chart·이미지·DB·로그 디스크, 기본 Keycloak 로그인 |
| Monitoring | [지표 수집·대시보드](monitoring/README.md) | chart·저장 디스크·Grafana 계정, 기본 공용 HTTPS |
| Headlamp | [Kubernetes 운영 화면](headlamp/README.md) | Keycloak client·관리자 그룹·모든 API server의 OIDC 인증 |
| FTP | [노드별 파일 수신](ftp/README.md) | 선택 노드·포트·저장 경로·계정 파일, passive 접속 |
| Portal | [업무 포털](portal/README.md) | 외부 PostgreSQL·Keycloak·MinIO·이미지·업무 파일 저장소, migration |

## 공통 준비와 운영

| 하려는 일 | 원본 문서 |
| --- | --- |
| 서버·네트워크·서비스·미러·운영 위치 확인 | [사내 인프라 정보](shared/docs/infrastructure/README.md) |
| 클러스터 설치·상태 조회·운영·kubectl 참고 | [공통 문서 색인](shared/docs/README.md) |
| 서버 앱 선택·checkout 범위 변경 | [선택 checkout](shared/docs/operations/checkout.md) |
| env 입력과 Secret 전달 | [환경설정](shared/docs/configuration/environment.md) |
| 인증서·CA 추출과 갱신 | [인증서 관리](shared/docs/certificates/README.md) |
| 공용 HTTPS·VIP·Worker 확장 | [Ingress 안내](shared/docs/ingress/README.md) |
| Git 갱신·서버 파일 관리 | [CP1 운영](shared/docs/operations/files.md) |

## 검사와 실행

준비 단계와 실제 클러스터 변경을 구분합니다. Make 명령은 루트 Makefile이 소유합니다.

```bash
# 저장소의 배포 원본을 검사합니다. 실제 env·클러스터 상태 검사는 앱 안내를 따릅니다.
make server-check APP=keycloak PROFILE=prod
```

- 앱별 chart·Helm이 필요한 경우 해당 앱의 준비 문서부터 수행합니다. `platform` 그룹 전체 검사도 각 앱의 준비물이 필요합니다.
- 실제 env는 [환경설정 검사](shared/docs/configuration/environment.md#설정-검사), 적용과 기동은 각 앱의 배포 절차를 따릅니다.
- 공용 Ingress만 준비할 때는 [Traefik 셋업](shared/docs/ingress/setup.md), 전달용 YAML은 [Keycloak 운영](keycloak/docs/08-operations.md)을 따릅니다.
- 서버의 선택 checkout에서는 앱별 `server-check`를 사용합니다. 전체 개발 checkout의 `k8s-render`는 로컬·서버 전체, `k8s-render-local`은 로컬, `k8s-render-server`는 Keycloak·Portal 서버 원본을 렌더링합니다.

## 소유권

| 위치 | 소유하는 내용 |
| --- | --- |
| `deploy/<app>/` | 앱 설치·운영 문서, env·manifest·Helm values·서버 실행 도구 |
| `deploy/shared/` | 공통 정의·도구·인증서·Ingress·인프라 정보 |
| `apps/<app>/` | 제품 코드·이미지 빌드 소스. 서버에서 빌드할 때만 추가 |
| `local/<app>/` | 외부 PC 개발 설정·mock·kind·실행 도구 |

앱 경로·서버 선택 그룹의 원본은 [apps.json](shared/apps.json)입니다.
`platform`은 Portal 외 서비스, `all`은 Portal을 포함합니다. 선택 checkout은 이전 범위를 교체합니다.
서버 검사·렌더·배포는 `apps`·`local`·루트 `docs` 없이 수행하며, 빌드에만 `--with-source`를 사용합니다.
외부 PC 개발은 전체 개발 checkout의 [local 안내](../local/README.md)를 따릅니다.

운영 env는 일반 설정과 비밀번호·토큰을 같은 파일에 넣고 비공개 Git에서 관리합니다.
도구는 지정한 env 하나를 읽습니다. Web에 공개되는 설정에는 비밀값을 넣지 않습니다.
CP1의 실제 외부 설정 경로는 [운영 위치 원본](shared/docs/infrastructure/operations.md)에서 확인합니다.
인증서·개인키·생성 YAML은 원본과 구분합니다. 인증서·개인키는 Git에 넣지 않고 생성 YAML은 직접 수정하지 않습니다.

서버 배포는 Kubernetes를 사용합니다. `portal/compose/test.yml`과 `portal/env/test/`는 CI API 검사용입니다.
보조 Compose의 상대 경로는 Compose 파일 기준이며 개발용 DB·API 검사는 `local/shared/compose`가 소유합니다.
Keycloak 관리자·전용 DB·사내 OIDC는 Keycloak, Portal client 등록 입력은 Portal이 소유합니다.

## 문서를 추가하거나 수정할 때

- 앱 README는 작업 선택과 설치 순서, `<app>/docs/`는 목적별 상세 절차를 소유합니다. 파일명은 소문자 kebab-case를 사용하며 번호는 실행 단계에만 씁니다.
- Job·overlay·입력 템플릿 옆 README에는 해당 원본의 역할·사용 조건과 상세 절차 링크를 둡니다.
- 공통 절차는 `shared/docs/`, 운영 현황은 `shared/docs/infrastructure/`의 주제별 원본에 둡니다. 앱별 명령·전체 운영 표를 다른 문서에 반복하지 않습니다.
- 절차는 목적·준비물 → 실행 위치·입력 → 명령 → 기대 결과·실패 확인 → 다음 단계로 작성합니다. 조회·검사와 실제 적용·삭제를 구분합니다.
- 문서 이동 시 내부 링크와 도구의 안내 경로를 새 원본으로 갱신합니다. 이전 경로·앵커의 호환 안내는 보존 요청이 있을 때만 둡니다.
- 현재 동작과 제약을 설명하고 확인 날짜·변경 경위·완료 기록은 Git 이력으로 추적합니다. 검증 규칙은 [배포 지침](AGENTS.md)을 따릅니다.
