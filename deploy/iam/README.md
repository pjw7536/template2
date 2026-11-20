# 권한관리(IAM) 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

[권한관리 웹](../../apps/iam/README.md)이 쓰는 Keycloak 설정을 준비하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 권한관리 웹이 로그인하고 Keycloak Admin API를 호출하는 데 필요한 client·그룹·관리 권한 준비 |
| namespace | 없음. 클러스터 워크로드 정의는 아직 없습니다(전환 미완료). Keycloak 설정만 배포합니다 |
| 대상 | Keycloak의 업무 realm(`etch`) |
| 배포 명령 | `make ops-deploy APP=iam` = 준비 검사 → `iam-check`(계획만 출력) → `iam-up`(적용) |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 출력의 `적용 완료` |
| 먼저 필요한 것 | Keycloak 배포와 realm·User Profile 설정(`keycloak-setup`), 권한관리 웹의 공개 주소 |

## 구성

`scripts/setup_keycloak.py`가 대상 realm에 다음을 준비합니다. 다시 실행해도 같은 결과입니다.

| 대상 | 내용 |
| --- | --- |
| client `iam` | public client, 표준 흐름 + PKCE S256, redirect `<IAM_PUBLIC_URL>/*`, web origin은 IAM 주소 |
| client scope | `fullScopeAllowed=false`, realm-management `view-users`·`query-users`·`query-groups`·`manage-users`만 허용 |
| 그룹 `/iam/platform-admins` | 위 4개 관리 role. 가입한 사용자만 권한관리 웹을 사용 |
| client `org` 관리 권한 | 플랫폼 관리자가 소속별 역할 client 하나만 조회·관리. `org` client는 [소속별 역할 반영](../keycloak/docs/02-configure.md)이 만듭니다 |
| realm 관리 이벤트 | 기록과 상세 기록을 켬 |

워크로드가 없으므로 smoke·배포 기록·대조는 수행하지 않습니다. 권한관리 웹의 컨테이너 이미지와 Kubernetes 정의는 [앱 문서](../../apps/iam/README.md)의 개발 실행만 있습니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| Keycloak 배포와 realm 설정 | `make keycloak-smoke KUBE_CONTEXT="<context>"` |
| 소속별 역할 client `org` 생성([소속별 역할](../keycloak/docs/02-configure.md)) | `make keycloak-org-sync`가 `계획: 변경 없음` 또는 변경 계획을 출력 |
| 권한관리 웹의 공개 주소를 `IAM_PUBLIC_URL`에 입력. 저장소 파일을 고칠 수 없으면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 복사본에 입력 | `make iam-check KUBE_CONTEXT="<context>"` |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `IAM_ENV` | IAM env 경로 | `deploy/iam/env/prod.env` |
| `KEYCLOAK_ENV` | 관리자 계정과 Keycloak 주소를 읽는 Keycloak env 경로 | `deploy/keycloak/env/prod.env` |

env 파일의 키입니다. 같은 이름의 환경변수를 주면 그 값이 우선합니다.

| 키 | 의미 |
| --- | --- |
| `IAM_PUBLIC_URL` | 권한관리 웹의 공개 주소(HTTPS, 경로 없음). 비어 있으면 검사가 멈춥니다 |
| `KEYCLOAK_TARGET_REALM` | 설정을 적용할 업무 realm. `master`에는 적용하지 않습니다 |

관리자 접속은 [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)의 방법을 씁니다. Keycloak 인증서를 검증할 사내 CA 묶음이 있으면 자동으로 사용합니다.

## A. 최초 설치

1. [변경] 배포. `iam-check`가 계획을 출력하고 `iam-up`이 적용합니다.
   ```bash
   make ops-deploy APP=iam KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `계획:` 줄들과 `적용 완료`가 있습니다.
2. [변경] 앱 역할 목록을 권한관리 웹이 읽도록 반영합니다. dry-run 뒤 적용합니다.
   ```bash
   make keycloak-access-apply
   make keycloak-access-apply KEYCLOAK_ACCESS_APPLY=1
   ```
   성공: 다시 실행한 dry-run이 `계획: 변경 없음`.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

플랫폼 관리자 지정(`/iam/platform-admins` 그룹 가입)은 요청에 대상 사용자가 있을 때 [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)로 수행합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| `scripts/setup_keycloak.py`, 권한관리 웹 주소 | [변경] `make ops-deploy APP=iam KUBE_CONTEXT="<context>"` |
| 적용 없이 계획만 확인 | [검사] `make iam-check KUBE_CONTEXT="<context>"` |
| 앱 역할 카탈로그(`deploy/keycloak/access/catalog.json`) | [변경] A-2 |

## C. 배포 후 확인

[검사] 다시 실행한 계획에 새로 만들 대상이 없는지 확인합니다.

```bash
make iam-check KUBE_CONTEXT="<context>"
```

성공: `dry-run 완료`가 출력되고 계획에는 client 갱신과 role 연결만 남습니다. 로그인 확인은 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인)을 따릅니다.

## 문제 해결과 멈춤 조건

| 증상 | 원인과 조치 |
| --- | --- |
| `IAM_PUBLIC_URL에는 HTTPS 주소 또는 loopback HTTP 주소를 지정하세요` | env의 `IAM_PUBLIC_URL`이 비었거나 형식이 다름. 사전 준비의 세 번째 행 |
| `Keycloak 연결 또는 응답 처리 실패` | Keycloak 공개 주소의 DNS·CA. `make keycloak-smoke KUBE_CONTEXT="<context>"`로 확인 |
| `Keycloak … 요청 실패 (HTTP 401)` / `(HTTP 403)` | 관리자 계정. [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)의 계정 위치 확인 |
| `client 'org'가 없습니다` | [변경] `make keycloak-org-sync KEYCLOAK_ORG_APPLY=1` 뒤 다시 실행 |

다음이면 멈추고 보고합니다.

- `기존 client 'iam'가 public client가 아닙니다`. 기존 client를 지우거나 다시 만들지 않습니다.
- `admin-permissions client가 없습니다`. Keycloak 버전과 세분화 관리 권한 기능이 필요하며 Keycloak 설정을 바꾸지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [권한관리 웹](../../apps/iam/README.md) | 화면 기능, 권한 모델, 개발 실행 |
| [Keycloak 설정](../keycloak/docs/02-configure.md) | 소속 그룹, 소속별 역할, 앱 역할 카탈로그 |
