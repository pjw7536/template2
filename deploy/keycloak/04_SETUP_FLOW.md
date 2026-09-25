# 04. Keycloak 단계별 설정

[시작 안내](README.md) · 이전: [서버 설치](01_SERVER_SETUP.md) · 입력: [환경변수](env/02_ENVIRONMENT.md) · 필드 참고: [매핑 계약](06_CLAIMS.md)

서버가 실행 중이고 `etch-sso` namespace의 `keycloak-runtime`에 실제 관리자 계정이 준비돼 있어야 합니다.
각 실행 파일은 **지정한 단계만 실행**합니다. 다른 단계를 자동으로 이어서 실행하지 않습니다.
대상 realm은 현재 배포 계약인 `etch`, IdP alias는 `oidc`입니다.

| 순서 | 작업 | 실행 파일 | Make 명령 |
| --- | --- | --- | --- |
| 0 | Realm 생성 | [00-create-realm.sh](scripts/00-create-realm.sh) | `keycloak-realm-setup` |
| 1 | Identity Provider 생성/갱신 | [01-create-idp.sh](scripts/01-create-idp.sh) | `keycloak-idp-setup` |
| 2 | User Profile 등록 | [02-register-user-profile.sh](scripts/02-register-user-profile.sh) | `keycloak-profile-setup` |
| 3 | IdP mapper 설정 | [03-sync-idp-mappers.sh](scripts/03-sync-idp-mappers.sh) | `keycloak-idp-mappers-setup` |
| 4 | Portal client·token mapper | [04-setup-portal-client.sh](scripts/04-setup-portal-client.sh) | `keycloak-portal-client-setup` |
| 5 | 소속·SDWT 그룹 권한 (선택) | [05-setup-sdwt.sh](scripts/05-setup-sdwt.sh) | `keycloak-sdwt-init` |

현재처럼 Realm과 provider가 정상 동작한다면 **2번부터 진행**합니다.
**Portal 연결은 나중에 해도 됩니다.** 2·3번까지 먼저 완료하고 Portal 준비가 끝나면 4번을 실행합니다.
2·3번에는 Portal client ID·secret·env 파일이 필요하지 않습니다.
기존 `make keycloak-oidc-setup` 통합 명령은 1~3번을 함께 실행하는 호환 경로로 유지됩니다.
단계별 명령과 통합 명령을 동시에 실행하지 마세요. 같은 관리 ConfigMap과 설정을 사용합니다.

## 준비

Python 3.10+·Bash·kubectl이 필요합니다. 저장소 루트에서 실행합니다.
0~4번은 명시한 context를 사용하며 현재 context를 바꾸지 않습니다.

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p '설정할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak
```

저장소 이동·도구 확인·입력 파일 편집부터 로그 확인까지의 실행 예시는
[Discovery 실행 안내](05_DISCOVERY_SETUP.md#3-실행-위치와-연결-조건)를 참고합니다.

## 0. Realm 생성

```bash
make keycloak-realm-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

직접 실행:

```bash
bash deploy/keycloak/scripts/00-create-realm.sh --context "$KEYCLOAK_KUBE_CONTEXT"
```

- `etch`가 없으면 [기본 realm 정의](k8s/server/etch-realm.json)로 생성합니다.
- 이미 있으면 갱신하지 않고 종료합니다. 사용자·client·프로필도 보존합니다.
- IdP client ID·secret이나 discovery 접속은 필요하지 않습니다.
- 확인: Admin Console의 realm 목록에 `etch`가 표시됩니다.

## 1. Identity Provider 생성

`deploy/keycloak/env/prod.env`의 사내 client ID·secret을 입력합니다.
`CORP_OIDC_DISCOVERY_URL`, `client_secret_post` 인증 방식, 서명 검증은 기존 값을 사용합니다.

```bash
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

직접 실행 또는 별도 env 입력:

```bash
bash deploy/keycloak/scripts/01-create-idp.sh --context "$KEYCLOAK_KUBE_CONTEXT" --env deploy/keycloak/env/prod.env
```

- Discovery → OIDC Secret → IdP Job까지만 수행합니다.
- User Profile과 mapper는 변경하지 않습니다.
- 확인: `Identity providers → oidc`에서 연결값과 실제 사내 로그인.
- 세부 입력 계약: [Discovery 안내](05_DISCOVERY_SETUP.md).

기존 사용자에 이전 저장 이름이 남아 있다면 [저장 이름 전환](06_CLAIMS.md#기존-사용자-저장-이름-전환)의 2번 프로필 → 값 복사 → 3번·4번 순서를 먼저 확인합니다.

## 2. User Profile 등록

```bash
make keycloak-profile-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

직접 실행:

```bash
bash deploy/keycloak/scripts/02-register-user-profile.sh --context "$KEYCLOAK_KUBE_CONTEXT"
```

- [account-user-profile.json](k8s/claims/account-user-profile.json)으로 사용자 필드·조회/편집 정책만 등록합니다.
- IdP·client·mapper를 변경하지 않습니다. Realm과 관리자 인증만 필요합니다.
- **기존 User Profile 정의는 교체**하며 커스텀 정의를 자동 병합하지 않습니다. 사용자 레코드·기존 속성값을 일괄 삭제하는 작업은 아닙니다.
- 확인: `Realm settings → User profile → Attributes`에서 `loginid`, `display_name`, `deptname`, `sabun`, `grdName` 등.
- 사용자 본인 조회, 관리자 편집 정책입니다. 기본 `username`, `email`, `firstName`, `lastName`도 포함됩니다.

## 3. IdP mapper 설정

2번의 프로필을 준비하고 realm의 `Email as username`이 꺼져 있는지 확인합니다.
켜져 있으면 mapper Job이 중단합니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

직접 실행:

```bash
bash deploy/keycloak/scripts/03-sync-idp-mappers.sh --context "$KEYCLOAK_KUBE_CONTEXT"
```

- User Profile을 다시 등록하지 않고 `oidc`의 mapper만 동기화합니다.
- 일반 속성 15개 + `epid-username` 1개를 설정합니다. 프로젝트에서 폐기한 mapper는 기존 계약대로 정리합니다.
- 확인: `Identity providers → oidc → Mappers`.

| 사내 수신 claim | Keycloak 내부 저장 필드 | 4번에서 앱에 발급하는 claim |
| --- | --- | --- |
| `userid` | 기본 `username` (EPID) | `userid` |
| `loginid` | `loginid` | `loginid` |
| `username` | `display_name` | `username` |
| `mail` | 기본 `email` | `mail` |
| `givenname` / `surname` | 기본 `firstName` / `lastName` | `givenname` / `surname` |
| `deptname` | `deptname` | `deptname` |
| `grdName` | `grdName` | `grdName` |

전체 계약은 [사용자 claim 매핑](06_CLAIMS.md)을 참고합니다.
`FORCE`로 사내 재로그인 시 갱신합니다. 사내에서 실제 claim을 발급해야 하며 mapper 생성만으로 값이 채워지지는 않습니다.

## 4. Portal client·token mapper 설정

`deploy/portal/env/prod/api.env`에 `OIDC_PROVIDER=keycloak`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`을 준비합니다.
**AD FS client와 다른 Portal 전용 client ID·secret**을 사용합니다.

```bash
make keycloak-portal-client-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
```

직접 실행:

```bash
bash deploy/keycloak/scripts/04-setup-portal-client.sh --context "$KEYCLOAK_KUBE_CONTEXT" --portal-env deploy/portal/env/prod/api.env
```

- Portal client와 token mapper 18개(사내 claim 16개 + 소속 2개)를 설정합니다.
- IdP 접속 정보·User Profile·IdP mapper를 변경하지 않습니다. Discovery 접속이나 사내 client secret은 필요하지 않습니다.
- 기존 Portal client의 secret·callback·Web origin 등은 env 값으로 갱신됩니다. 운영값을 확인하세요.
- 확인: 해당 client의 전용 client scope에 있는 Mappers와 실제 발급 토큰.
- 반환 claim은 사내 이름을 유지합니다. 전체 흐름은 `loginid → loginid → loginid`, `userid → 기본 username → userid`, `username → display_name → username`입니다.
- 이 단계는 Portal client에 mapper를 등록합니다. 다른 앱 client에 자동 전파되지는 않습니다. [앱 전환 확인 항목](06_CLAIMS.md#기존-사내-oidc-앱을-연결할-때)을 참고하세요.
- Portal API에도 같은 client 설정을 별도로 적용해야 합니다. [Portal client 계약](../portal/k8s/jobs/keycloak-client/README.md)을 따릅니다.

## 5. 소속·SDWT 그룹 권한 — 선택

이 단계는 Kubernetes Job 대신 기존 SDWT 도구의 관리 API·CSV 계약을 사용합니다.
[SDWT 안내](07_SDWT_SETUP.md)에 따라 관리자 접속 URL·인증 환경변수를 준비합니다.
client는 4번 등으로 미리 생성돼 있어야 합니다. 기본은 **dry-run**입니다.

```bash
# 서버 접속 없이 CSV만 검사합니다.
bash deploy/keycloak/scripts/05-setup-sdwt.sh --sdwts /absolute/path/sdwts.csv --users /absolute/path/users.csv --validate-only

# 변경 예정 내역을 확인합니다. 관리자 인증 환경변수가 필요합니다.
bash deploy/keycloak/scripts/05-setup-sdwt.sh --sdwts /absolute/path/sdwts.csv --users /absolute/path/users.csv --client portal

# 확인한 입력을 적용합니다.
bash deploy/keycloak/scripts/05-setup-sdwt.sh --sdwts /absolute/path/sdwts.csv --users /absolute/path/users.csv --client portal --apply
```

Make를 사용할 때는 기존 `make keycloak-sdwt-init`의 `KEYCLOAK_SDWTS_CSV`, `KEYCLOAK_USERS_CSV`,
`KEYCLOAK_SDWT_CLIENTS`, `KEYCLOAK_SDWT_VALIDATE_ONLY`, `KEYCLOAK_SDWT_APPLY` 입력을 그대로 사용합니다.
`user_sdwt_prod`·`line_id`는 실제 소속이며 접근 권한은 별도 `/{SDWT}/admin|user|viewer` 그룹입니다.
기존 사용자의 소속·권한은 재등록으로 덮어쓰지 않습니다.

## 완료 확인과 실패 재실행

0~4번은 각각 최신 관리 ConfigMap을 준비하고 자신의 Job만 재생성한 뒤 완료를 기다립니다.

| 단계 | Job 이름 |
| --- | --- |
| 0 | `keycloak-realm-setup` |
| 1 | `keycloak-oidc-setup` |
| 2 | `keycloak-user-profile-setup` |
| 3 | `keycloak-idp-mappers-setup` |
| 4 | `portal-keycloak-client` |

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-user-profile-setup
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-idp-mappers-setup
```

실패 시 해당 Job 로그를 확인하고 원인을 수정한 뒤 해당 단계만 재실행합니다.
실행 도중 적용된 설정은 자동 롤백하지 않습니다. 기존 realm과 계정 연결 정책은 유지합니다.
마지막으로 시험 계정이 사내 인증을 다시 거치게 하고 사용자 속성, 새 Portal 토큰, 앱 로그인·권한을 확인합니다.
