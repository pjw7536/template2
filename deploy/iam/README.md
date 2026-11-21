# 권한관리(IAM) 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

관리 호스트의 저장소 루트에서 [권한관리 웹](../../apps/iam/README.md)이 쓰는 Keycloak 설정을 적용합니다. 명령의 단계 표시는 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | Keycloak에서 IAM 로그인, 조직 역할, 플랫폼 관리자 권한과 앱 역할 카탈로그 준비 |
| namespace | 없음. IAM 웹의 운영 이미지·Kubernetes 정의는 아직 없습니다 |
| 대상 | `KEYCLOAK_ENV`가 가리키는 Keycloak과 `IAM_ENV`의 업무 realm(기본 `etch`) |
| 웹 공개 주소 | [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)의 IAM 항목. Keycloak의 redirect URI와 web origin에 사용 |
| 배포 명령 | `make ops-deploy APP=iam` → 준비 검사 → `iam-check` → `iam-up`(적용과 조회 검증) |
| 완료 기준 | 요약 `failedStep`이 `null`이고 `IAM Keycloak 설정 검증 통과.`와 `IAM Keycloak 설정 적용 완료.` 출력 |
| 먼저 필요한 것 | Keycloak 배포와 기본 realm 설정, IAM 웹 공개 주소 |

## 구성

같은 관리자 연결과 realm으로 다음 설정을 순서대로 반영합니다.

| 대상 | 내용 |
| --- | --- |
| 조직 역할 | 기존 `/org` 트리에서 `org` client·소속 역할·`org-claims`를 구성 |
| IAM client | public client `iam`, 표준 흐름·PKCE S256, 공개 주소에 대한 redirect·web origin, `fullScopeAllowed=false`와 필요한 관리 역할 매핑 |
| 관리자 그룹과 정책 | `/iam/platform-admins`, `org` client에 한정한 세분화 관리 권한 v2, realm의 관리 이벤트 상세 기록 |
| 앱 역할 카탈로그 | 이미 등록된 앱 client의 역할과 `/iam`의 `iam.catalog` 속성 |
| 플랫폼 관리자 | `IAM_PLATFORM_ADMIN_USERNAMES`에 명시한 기존 사용자를 관리자 그룹에 추가 |

IAM은 설정 전용 앱입니다. Kubernetes 배포 기록과 대조는 생략되므로 요약의 `driftResultCode: 0`과 함께 `iam-up`의 검증 출력을 확인합니다.

## 사전 준비

| 준비 작업 | 완료 확인 |
| --- | --- |
| [Keycloak 배포 및 기본 설정](../keycloak/README.md#a-최초-설치) | [검사] `make keycloak-smoke KUBE_CONTEXT="<context>"` 통과 |
| 관리 호스트에서 Keycloak 관리 API 접속 | [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)의 계정·CA 입력 경로 확인 |
| 운영 IAM env 준비 | 저장소 기본 공개 주소를 사용합니다. [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)을 쓰는 환경은 기존 복사본의 공개 주소를 확인하고 필요 시 기존 관리자 username을 입력합니다. 아래 `iam-check` 통과 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `IAM_ENV` | IAM 설정 파일 경로 | `deploy/iam/env/prod.env` |
| `KEYCLOAK_ENV` | 관리자 로그인과 접속 주소를 읽는 Keycloak env 경로 | `deploy/keycloak/env/prod.env` |

`IAM_ENV`의 설정 키입니다. 명령 환경에 같은 이름의 값을 지정하면 그 값이 우선합니다.

| 키 | 의미 |
| --- | --- |
| `IAM_PUBLIC_URL` | IAM 웹을 서비스할 HTTPS 주소. 경로 없이 입력. 운영 기본값은 [prod.env](env/prod.env) |
| `KEYCLOAK_TARGET_REALM` | 설정을 적용할 업무 realm. 기본 `etch` |
| `IAM_PLATFORM_ADMIN_USERNAMES` | 추가할 기존 Keycloak username을 쉼표로 구분. 기존 그룹 가입은 유지하며 빈 값이면 추가하지 않음 |

`KUBE_CONTEXT`는 배포 준비 검사에 사용합니다. 실제 설정 대상 Keycloak과 realm은 위 입력으로 결정하며 `IAM 설정 대상 realm:` 줄에서 realm을 확인할 수 있습니다. 운영 명령에는 검사에 사용한 입력 경로를 그대로 붙입니다.

## A. 최초 설치

1. [검사] 필요한 변경과 대상 realm을 확인합니다. `<Keycloak env 경로>`는 Keycloak을 배포할 때 사용한 파일입니다.
   ```bash
   make iam-check KUBE_CONTEXT="<context>" IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
   ```
   `IAM 설정 대상 realm:`이 운영 대상과 일치하고 `dry-run 완료.`가 나오면 적용 단계로 진행합니다.
2. [변경] 검사에 사용한 입력으로 설정을 적용합니다.
   ```bash
   make ops-deploy APP=iam KUBE_CONTEXT="<context>" IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
   ```
   `IAM Keycloak 설정 검증 통과.`와 `IAM Keycloak 설정 적용 완료.`가 나오고 요약의 `failedStep`이 `null`이면 적용 성공입니다. 앱 client가 없어 건너뛰었다는 경고가 있으면 해당 앱 배포 후 IAM을 다시 실행합니다.
3. [조회] [배포 후 확인](#c-배포-후-확인)으로 적용 상태를 확인합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| 조직 역할·관리자 목록·앱 역할 카탈로그, 새 앱 client 등록 | [변경] A의 검사·적용 절차를 다시 실행 |
| 사용 중인 IAM 웹의 공개 주소 변경 | [승인] 새 주소와 영향받는 로그인 경로를 보여 준 뒤 A의 적용 명령으로 반영 |
| 적용 상태만 조회 | [조회] C의 `iam-verify` 실행 |

## C. 배포 후 확인

[조회] 배포와 같은 입력으로 Keycloak 설정을 다시 읽습니다.

```bash
make iam-verify IAM_ENV="<IAM env 경로>" KEYCLOAK_ENV="<Keycloak env 경로>"
```

`계획: 변경 없음`과 `IAM Keycloak 설정 검증 통과.`가 성공 기준입니다. `설정 검증 불일치`가 나오면 오류의 변경 항목을 확인한 뒤 A를 다시 실행합니다. IAM 웹이 호스팅된 경우 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인)의 방법으로 지정한 플랫폼 관리자의 로그인과 권한 화면을 확인합니다.

웹을 공개할 때는 [업무 HTTPS 인증서](../shared/docs/infrastructure/network.md#업무-https-인증서)의 IAM 항목과 [대기 작업](../shared/docs/infrastructure/pending.md#3-앱-배포)의 웹 공개 조건을 확인합니다.

## 문제 해결과 멈춤 조건

| 증상 | 원인과 조치 |
| --- | --- |
| `IAM_PUBLIC_URL` 주소 검사 실패 | 운영 입력에 IAM 웹의 HTTPS 주소를 경로 없이 넣고 다시 검사 |
| `Keycloak 연결 또는 응답 처리 실패`, HTTP 401·403 | [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)에서 배포에 쓴 env의 주소·DNS·CA·관리 권한 확인 |
| `IAM_PLATFORM_ADMIN_USERNAMES의 기존 사용자` 조회 실패 | 업무 realm과 정확한 username 확인. 사내 로그인으로 처음 등록되는 사용자라면 먼저 로그인한 뒤 IAM 재실행 |
| `Keycloak에서 세분화 관리 권한 v2를 지원해야 합니다`, `admin-permissions client가 없습니다` | Keycloak 버전과 지원 기능을 확인할 때까지 IAM 적용 중단 |
| 기존 `iam` client가 public client가 아니거나 기존 권한의 유형이 다름 | 대상 realm과 객체를 확인할 때까지 중단 |

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [권한관리 웹](../../apps/iam/README.md) | 화면 기능, 권한 모델, 개발 실행 |
| [Keycloak 설정](../keycloak/docs/02-configure.md) | 소속 트리 입력과 앱 역할 카탈로그 |
