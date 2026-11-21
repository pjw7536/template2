# Etch Members 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

관리 호스트의 저장소 루트에서 [Etch Members](../../apps/iam/README.md) 웹과 업무 부하 API를 배포합니다. 명령의 단계 표시는 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | IAM 웹과 업무 부하 API를 공개하고 Keycloak 로그인·권한을 구성 |
| namespace | `iam` |
| 대상 | `KEYCLOAK_ENV`가 가리키는 Keycloak과 `IAM_ENV`의 업무 realm(기본 `etch`) |
| 웹 공개 주소 | [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)의 IAM 항목. Ingress, Keycloak redirect URI와 web origin에 사용 |
| 배포 명령 | `make ops-deploy APP=iam` → 준비 검사 → `iam-check` → `iam-image` → `iam-up` → `iam-smoke` → 대조 |
| 완료 기준 | `failedStep`이 `null`, `driftResultCode`가 `0`, IAM 로그인과 업무 부하 화면 확인 |
| 먼저 필요한 것 | 공용 Traefik·TLS·Keycloak·Zot, 빌드 도구, 저장소 Worker와 데이터 디스크 |

## 구성

- 웹: Zot의 `iam-web` 이미지와 공용 Traefik으로 제공합니다. 런타임 `config.js`는 공개 Keycloak URL과 realm으로 만듭니다.
- API: Zot의 `iam-api` 이미지가 업무 부하의 WSGI 앱을 실행합니다. 웹이 같은 origin의 `/api/workload/` 요청을 내부 API Service로 전달합니다.
- 데이터: 업무 부하 SQLite는 Worker의 로컬 디스크에 정적 Retain PV와 PVC로 보존합니다. API replica 한 개가 DB를 사용합니다. [앱 배치와 스토리지](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)
- 빌드: 이미지별 소스와 빌드 env 내용으로 tag를 정하고, Zot에 빠진 tag만 빌드해 push합니다. [이미지 빌드](../README.md#이미지-빌드-도구)

같은 관리자 연결과 realm으로 아래 Keycloak 설정을 반영합니다.

| 대상 | 내용 |
| --- | --- |
| 조직 역할 | 기존 `/org` 트리에서 `org` client·소속 역할·`org-claims`를 구성 |
| IAM client | public client `iam`, 표시 이름 `Etch Members`, PKCE S256, redirect·web origin, `fullScopeAllowed=false`, 필요한 관리 역할과 `display_name`·`loginid` mapper |
| 관리자 그룹과 정책 | `/iam/platform-admins`, `org` client에 한정한 세분화 관리 권한 v2, realm의 관리 이벤트 상세 기록 |
| 앱 역할 카탈로그 | 이미 등록된 앱 client의 역할과 `/iam`의 `iam.catalog` 속성 |
| 플랫폼 관리자 | 그룹이 비어 있으면 env로 최초 관리자 등록, 이후 Etch Members 화면에서 추가 |

## 사전 준비

| 준비 작업 | 완료 확인 |
| --- | --- |
| [공용 Traefik](../shared/ingress/README.md)과 [Zot](../registry/README.md) 배포 | [검사] `make ops-preflight APP=iam KUBE_CONTEXT="<context>"`의 선행 앱 줄이 `[통과]` |
| [Keycloak 배포 및 기본 설정](../keycloak/README.md#a-최초-설치) | [검사] `make keycloak-smoke KUBE_CONTEXT="<context>"` 통과 |
| 관리 호스트에서 Keycloak 관리 API 접속 | [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)의 계정·CA 입력 경로 확인 |
| IAM 공개 주소의 기존 인증서와 사내 CA, 빌드 도구와 Zot push 계정 | [검사] `make ops-preflight APP=iam KUBE_CONTEXT="<context>"`의 공용 TLS·CA·빌드 도구가 `[통과]` 또는 `[자동 준비]`. push 계정은 [Zot 입력](../registry/README.md#입력) 확인 |
| IAM 데이터 Worker의 `/appdata`가 데이터 디스크에 마운트된 상태 | [Worker 디스크 확인](../shared/docs/infrastructure/operations.md#1-디스크-확인--각-worker)의 결과 확인 |
| 운영 IAM env와 실제 관리자 사용자 | [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 저장소 밖 복사본을 준비하고 `make iam-check KUBE_CONTEXT="<context>"` 통과 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `IAM_ENV` | IAM 설정 파일 경로 | `deploy/iam/env/prod.env` |
| `IAM_BUILD_ENV` | 사내 이미지·npm·PyPI 미러 입력 | `deploy/iam/env/build.env` |
| `KEYCLOAK_ENV` | 공개 Keycloak URL과 관리자 접속 정보 | `deploy/keycloak/env/prod.env` |
| `REGISTRY_ENV` | `REGISTRY_HOST`를 읽는 Zot env 경로 | `deploy/registry/env/k8s.env` |
| `REGISTRY_PUSH_ENV` | 새 tag 게시에 사용하는 Zot 계정 파일 | `deploy/registry/env/push-initial.env` |

`IAM_ENV`의 설정 키입니다. 앱 배포에서 사용하는 공개 주소와 realm은 이 파일에 맞춥니다.

| 키 | 의미 |
| --- | --- |
| `IAM_PUBLIC_URL` | IAM 웹을 서비스할 HTTPS 주소. 경로 없이 입력. 운영 기본값은 [prod.env](env/prod.env) |
| `KEYCLOAK_TARGET_REALM` | 설정을 적용할 업무 realm. 기본 `etch` |
| `IAM_PLATFORM_ADMIN_USERNAMES` | 최초 관리자의 Keycloak `username`(EPID) 한 개. 관리자 그룹이 비어 있고 입력값이 있을 때만 등록 |
| `IAM_STORAGE_NODE` | 업무 부하 API와 정적 PV를 배치할 Worker의 `kubernetes.io/hostname` |
| `IAM_DATA_HOST_PATH` | Worker의 SQLite 전용 저장 폴더. 기본 `/appdata/iam` |

기존 IAM 설정용 env를 그대로 사용할 때는 두 스토리지 키를 추가합니다. 기본값과 다른 파일을 쓰면 검사·빌드·배포·렌더·대조에 같은 경로를 지정합니다. Keycloak 설정만 다루는 `iam-keycloak-setup`과 `iam-verify`를 배포와 같은 값으로 실행할 때는 별도 origin·realm 환경변수도 대조합니다.

사내 SSO 발급값과 최초 관리자 EPID를 `identity.env`에 입력할 때는 [공용 운영 입력 준비](../shared/docs/operations/02-deploy.md#공용-운영-입력-준비)가 출력한 `KEYCLOAK_ENV`, `IAM_ENV`와 선택 Zot 인자를 사용합니다.

## A. 최초 설치

1. [검사] 대상 클러스터·선행 앱·TLS·빌드 도구와 입력을 확인합니다. 외부 env 경로는 사용 중인 파일에 맞춥니다.
   ```bash
   make ops-preflight APP=iam KUBE_CONTEXT="<context>" IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
   ```
   `[배포 차단]`이 없으면 적용 단계로 진행합니다. `[자동 준비]`는 다음 단계가 처리합니다. 막힌 항목은 출력의 `볼 곳`을 따릅니다.
2. [변경] 배포 준비, IAM 검사, Zot 게시, Keycloak 설정과 워크로드 적용, smoke·대조를 실행합니다.
   ```bash
   make ops-deploy APP=iam KUBE_CONTEXT="<context>" IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
   ```
   `IAM Keycloak 설정 검증 통과.`, `IAM 웹·업무 부하 API 배포 완료`, `smoke 통과: iam`과 함께 요약의 `failedStep`이 `null`, `driftResultCode`가 `0`이면 적용 성공입니다. 앱 client가 없어 건너뛰었다는 경고는 해당 앱 client를 등록한 뒤 IAM 설정을 다시 적용합니다.
3. [조회] [배포 후 확인](#c-배포-후-확인)으로 적용 상태를 확인합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| 앱 코드·빌드 입력·워크로드 설정 | [변경] A의 검사·적용 절차를 다시 실행 |
| IAM client 이름과 mapper·조직 역할·앱 역할 카탈로그 | [변경] `make iam-keycloak-setup IAM_KEYCLOAK_APPLY=1 IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"`. 성공은 `IAM Keycloak 설정 적용 완료.` |
| 플랫폼 관리자 추가 | [변경] 기존 플랫폼 관리자가 [Etch Members 화면](../../apps/iam/README.md#플랫폼-관리자-추가)에서 등록 |
| 사용 중인 IAM 웹의 공개 주소 변경 | [승인] 새 주소와 영향받는 로그인 경로를 보여 준 뒤 A의 적용 명령으로 반영 |
| 적용 상태만 조회 | [조회] C의 `iam-verify` 실행 |

## C. 배포 후 확인

[조회] 워크로드 준비·PVC·Traefik HTTPS 경로와 Keycloak 설정을 확인합니다. 배포에 사용한 파일 경로를 같게 지정합니다.

```bash
kubectl --context "<context>" -n iam get deployments,pvc,ingress
make iam-smoke KUBE_CONTEXT="<context>" IAM_ENV="<IAM env 경로>"
make iam-verify IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
```

두 Deployment가 `Available`, PVC가 `Bound`, smoke가 `smoke 통과: iam`을 출력해야 합니다. smoke는 Ingress부터 웹 프록시를 거쳐 업무 부하 API와 SQLite 상태를 확인합니다. `iam-verify`는 `계획: 변경 없음`, `IAM Keycloak 설정 검증 통과.`가 성공 기준입니다. [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인)의 방법으로 플랫폼 관리자 로그인, 상단의 `이름(로그인 ID)`, 권한 화면과 업무 부하 월별 조회를 확인합니다.

## 문제 해결과 멈춤 조건

| 증상 | 원인과 조치 |
| --- | --- |
| `IAM_PUBLIC_URL` 주소 검사 실패 | 운영 입력에 IAM 웹의 HTTPS 주소를 경로 없이 넣고 다시 검사 |
| `Zot에 IAM 이미지가 없습니다` 또는 `ImagePullBackOff` | [변경] A의 이미지 게시 단계와 동일한 입력으로 다시 배포. pull 실패는 [Zot 노드 CA 신뢰](../registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)를 확인 |
| 기존 IAM PV·PVC 설정 불일치 | 기존 용량·경로·Worker·PVC 연결을 확인합니다. 실제 데이터 이동이 필요하면 [Worker 앱 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 따릅니다 |
| 공개 주소가 다른 Ingress에서 사용 중 | [조회] 해당 Ingress의 서비스 용도와 IAM 공개 주소를 확인 |
| `Keycloak 연결 또는 응답 처리 실패`, HTTP 401·403 | [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)에서 배포에 쓴 env의 주소·DNS·CA·관리 권한 확인 |
| `IAM_PLATFORM_ADMIN_USERNAMES의 기존 사용자` 조회 실패 | 업무 realm과 정확한 username 확인. 사내 로그인으로 처음 등록되는 사용자라면 먼저 로그인한 뒤 IAM 재실행 |
| 로그인에 성공했지만 Etch Members 접근 불가 | 관리자 그룹이 비어 있으면 최초 관리자 EPID를 입력하고 [업데이트](#b-업데이트)의 Keycloak 설정 명령을 실행합니다. 기존 관리자가 있으면 Etch Members에서 등록을 요청합니다. 등록 후 로그아웃하고 다시 로그인합니다. 이미 그룹에 가입한 계정은 `iam` 액세스 토큰의 `realm-management/manage-users` 역할을 확인합니다 |
| `Keycloak에서 세분화 관리 권한 v2를 지원해야 합니다`, `admin-permissions client가 없습니다` | Keycloak 버전과 지원 기능을 확인할 때까지 IAM 적용 중단 |
| 기존 `iam` client가 public client가 아니거나 기존 권한의 유형이 다름 | 대상 realm과 객체를 확인할 때까지 중단 |

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [Etch Members](../../apps/iam/README.md) | 화면 기능, 권한 모델, 개발 실행 |
| [Keycloak 설정](../keycloak/docs/02-configure.md) | 소속 트리 입력과 앱 역할 카탈로그 |
