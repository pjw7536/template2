# Keycloak 로그인·그룹·앱 연결

[앱 안내](../README.md)

- [Realm과 사내 로그인](#realm과-사내-로그인)
- [SDWT 그룹·사용자](#sdwt-그룹사용자)
- [앱 연결](#앱-연결)
- [사용자 필드와 claim](#사용자-필드와-claim)

## Realm과 사내 로그인

**목적:** Realm → 사내 IdP → User Profile → IdP mapper 순서로 사내 로그인을 준비합니다. 앱 client는 [앱 연결](#앱-연결)에서 만듭니다.

**준비물:** [서버 기동 확인](02-deploy.md#2-서버-기동-확인) 완료, `keycloak-runtime` Secret, 사내 AD FS client ID·secret.

### 실행 위치와 입력

서버 설치 때 사용한 저장소 루트의 Bash에서 실행합니다. 새 터미널이라면 context를 다시 선택합니다.

```bash
kubectl config get-contexts
read -r -p '설정할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get secret keycloak-runtime
```

각 Make 명령은 해당 설정 Job을 생성하고 완료될 때까지 최대 15분 기다립니다. Job을 별도로 apply하지 않습니다.
명령 하나가 성공한 것을 확인한 뒤 다음 단계로 넘어가며, 실패하면 [Job 결과 확인](#job-결과-확인)으로 원인을 해결합니다.

### 1. Realm 준비

```bash
make keycloak-realm-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

**기대 결과:** 서버 최초 import가 `etch`를 이미 만들었다면 존재 여부만 확인하고 기존 설정을 유지합니다.
Admin Console에 서버 설치 때의 관리자 계정으로 접속해 `etch` realm을 선택합니다. 이후 관리 화면 설정은 `master`가 아닌 `etch`에서 확인합니다.

### 2. 사내 Identity Provider 생성

[사내 IdP 입력](01-prepare.md#사내-identity-provider용-값)을 `deploy/keycloak/env/prod.env`에 작성합니다.
AD FS에는 `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint`가 redirect URI로 등록되어 있어야 합니다.

```bash
vi deploy/keycloak/env/prod.env
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$KEYCLOAK_KUBE_CONTEXT" --env deploy/keycloak/env/prod.env
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

다른 env 파일을 쓰면 두 명령에 같은 경로를 전달합니다(`--env`, `KEYCLOAK_ENV=`).

**기대 결과:** 검사가 `사전 검사 통과`를 출력하고, `Identity providers → oidc` 연결이 생성됩니다.

#### Discovery 해석 규칙

실행 호스트가 `CORP_OIDC_DISCOVERY_URL`의 JSON을 조회해 아래 값을 IdP Job에 전달합니다.
해석 결과는 임시 env와 `keycloak-oidc-settings` Secret으로 전달하며 원본 `prod.env`를 덮어쓰지 않습니다.

| Metadata 항목 | 사용 목적 | 필수 여부 |
| --- | --- | --- |
| `authorization_endpoint` | 브라우저의 사내 인증 주소 | 필수 |
| `token_endpoint` | 인증 코드를 토큰으로 교환 | 필수 |
| `issuer` | 토큰 발급자 검증. 받은 값을 그대로 사용 | 필수 |
| `jwks_uri` | 서명 검증용 공개키 | 필수 |
| `userinfo_endpoint` | 사용자 정보 추가 조회 | 제공 시 사용 |
| `end_session_endpoint` | 사내 로그아웃 | 제공 시 사용 |

- 필수 값이 없으면 검사가 중단됩니다. 선택 endpoint가 없으면 env의 `CORP_OIDC_USERINFO_URL`·`CORP_OIDC_LOGOUT_URL` 값이 있을 때만 사용하고 추정해서 만들지 않습니다.
- endpoint는 HTTPS여야 하고 서명 검증(`CORP_OIDC_VALIDATE_SIGNATURE=true`)이 필요합니다.
- `CORP_OIDC_CLIENT_AUTH_METHOD`는 metadata의 `token_endpoint_auth_methods_supported`에 있어야 합니다. 목록이 없으면 `client_secret_basic`만 지원하는 것으로 보므로 `client_secret_post` 설정은 검사에서 중단됩니다.
- `client_secret_post`는 Keycloak 화면의 `Client secret sent in the request body`에 해당합니다.
- Discovery는 credential·사용자 claim 값·접근 권한을 발급하지 않습니다.

| 접속 주체 | 필요한 연결 |
| --- | --- |
| 실행 호스트 | Discovery URL 접근과 CA 신뢰. 별도 CA 파일은 `SSL_CERT_FILE`로 지정 |
| Keycloak Pod | 사내 Token·JWKS·UserInfo endpoint 접근과 CA 신뢰 |
| 브라우저 | 사내 인증 주소와 공개 Keycloak 주소 접근 |

호스트의 CA 신뢰는 Pod에 자동 전달되지 않습니다. [TLS·CA 준비](01-prepare.md#tlsca-준비)를 참고합니다.
참고: [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).

### 3. User Profile 등록

```bash
make keycloak-profile-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

**기대 결과:** `Realm settings → User profile`에 `loginid`, `deptname`, `grdName`, `display_name`, `sabun` 등이 있습니다. 필드 정의는 [사용자 필드와 claim](#사용자-필드와-claim)에 있습니다.

### 4. 사내 claim 수신 mapper 설정

`Realm settings`에서 `Email as username`이 꺼져 있는지 확인한 뒤 실행합니다. 켜져 있으면 Job이 중단됩니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

**기대 결과:** `Identity providers → oidc → Mappers`에 일반 속성 mapper 15개와 `epid-username` 1개가 있습니다.
mapper 생성만으로 사용자 값이 채워지지 않으며 사내 로그인을 거쳐야 수신합니다.

### 5. SDWT 그룹 등록

SDWT 권한을 사용하면 [SDWT 그룹·사용자](#sdwt-그룹사용자)를 완료한 뒤 아래 완료 확인으로 돌아옵니다. 사용하지 않으면 생략합니다.

### 설정 완료 확인

브라우저에서 `<공개 Keycloak URL>/realms/etch/account/`를 열고 사내 provider를 선택해 시험 계정으로 로그인합니다.

| 확인 위치 | 완료 기준 |
| --- | --- |
| Account Console | 사내 인증을 거쳐 사용자 계정 화면에 도달 |
| Admin Console → Users → 시험 사용자 | 기본 username은 EPID, loginid·deptname·grdName 등 사내에서 제공한 값이 저장됨 |
| Users → 시험 사용자 → Identity provider links | 사내 `oidc` 연결 확인 |
| Groups / Users → Groups | SDWT 사용 시 준비한 그룹과 시험 사용자의 가입 확인 |

CSV로 사전 등록한 계정은 첫 사내 로그인에서 계정 연결 확인이 필요할 수 있습니다. EPID가 같다는 이유만으로 자동 연결을 가정하지 않습니다.

**다음 단계:** [앱 연결](#앱-연결). 앱의 토큰·로그인·권한 검증은 각 앱 연결 단계에서 수행합니다.

### Job 결과 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
read -r -p '로그를 확인할 Job 이름: ' KEYCLOAK_JOB_NAME
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs "job/$KEYCLOAK_JOB_NAME"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso describe job "$KEYCLOAK_JOB_NAME"
```

| 작업 | Make 명령 | 실행 파일 | Job 이름 |
| --- | --- | --- | --- |
| Realm | `keycloak-realm-setup` | `scripts/00-create-realm.sh` | `keycloak-realm-setup` |
| IdP | `keycloak-idp-setup` | `scripts/01-create-idp.sh` | `keycloak-oidc-setup` |
| User Profile | `keycloak-profile-setup` | `scripts/02-register-user-profile.sh` | `keycloak-user-profile-setup` |
| IdP mapper | `keycloak-idp-mappers-setup` | `scripts/03-sync-idp-mappers.sh` | `keycloak-idp-mappers-setup` |
| Portal client | `keycloak-portal-client-setup` | `scripts/04-setup-portal-client.sh` | `portal-keycloak-client` |
| SDWT | `keycloak-sdwt-init` | `scripts/05-setup-sdwt.sh` | Job 없이 관리자 API 사용 |

같은 Make 명령을 다시 실행하면 기존 Job을 삭제하고 새로 만듭니다. 원인을 해결하기 전에는 다음 단계로 넘어가지 않습니다.

## SDWT 그룹·사용자

**목적:** SDWT별 `admin`·`user`·`viewer` 그룹과 선택적으로 사용자를 사전 등록합니다. 앱 client는 필요하지 않습니다.

**준비물:** Realm·User Profile·IdP mapper 완료, 저장소 밖에 작성한 CSV, Keycloak 관리자 계정.
관리자 API를 직접 사용하며 Kubernetes Job이나 runtime Secret을 사용하지 않습니다. 실제 사용자 CSV와 인증정보는 Git에 넣지 않습니다.

### 1. 입력 파일 검사

[SDWT 템플릿](../inputs/sdwts.template.csv)과 [사용자 템플릿](../inputs/users.template.csv)을 저장소 밖 작업 경로에 복사합니다.
UTF-8 CSV로 저장하고 EPID·사번은 텍스트로 입력해 선행 0을 유지합니다. 헤더만 있는 파일은 사용할 수 없습니다.

SDWT–line CSV의 필수 헤더는 `user_sdwt_prod,line_id`입니다. SDWT 이름은 유일해야 하며 `/`를 포함할 수 없습니다.

```csv
user_sdwt_prod,line_id
SDWT-A,LINE-1
SDWT-B,LINE-1
```

사용자 CSV의 필수 헤더는 `userid,user_sdwt_prod`입니다. `userid`는 EPID이고 소속이 없으면 SDWT 칸을 비웁니다.
선택 헤더는 `sabun,loginid,username,mail,deptname,grdname_en`이며 저장 위치는 [사용자 필드와 claim](#사용자-필드와-claim)을 따릅니다.
Portal을 사용할 사용자는 `sabun`, `loginid`를 CSV에 포함하거나 사내 로그인에서 수신할 수 있어야 합니다.

```csv
userid,user_sdwt_prod,sabun,loginid,username,mail
90000001,SDWT-A,100001,example.user,예시사용자,user@example.invalid
```

예시는 가상 데이터입니다. 그룹만 준비한다면 사용자 CSV 경로는 비워 둡니다. 저장소 루트에서 서버 접속 없이 검사합니다.

```bash
read -r -p 'SDWT CSV 절대 경로: ' KEYCLOAK_SDWTS_CSV
read -r -p '사용자 CSV 절대 경로 (그룹만 만들면 Enter): ' KEYCLOAK_USERS_CSV
export KEYCLOAK_SDWTS_CSV KEYCLOAK_USERS_CSV
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1
```

**기대 결과:** `CSV 검증 완료: SDWT <n>개, 사용자 <n>명 (서버 연결 없음)`.

### 2. 관리자 인증 입력

URL은 realm 경로를 제외한 공개 HTTPS 주소입니다. 비밀번호는 입력 중 표시되지 않습니다.

```bash
read -r -p 'Keycloak 관리 접속 URL: ' KEYCLOAK_ADMIN_URL
read -r -p '관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p '관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_REALM=master
export KEYCLOAK_TARGET_REALM=etch
```

OS가 Keycloak 인증서를 신뢰하지 않으면 CA 파일을 지정합니다. 인증서 검증은 생략하지 않습니다.

```bash
read -r -p '관리 API를 신뢰할 CA PEM 절대 경로: ' KEYCLOAK_CA_FILE
export KEYCLOAK_CA_FILE
```

서비스 계정을 사용하면 `KEYCLOAK_ADMIN_CLIENT_ID`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `KEYCLOAK_ADMIN_REALM`으로 인증하며 client secret이 사용자 비밀번호보다 우선합니다.

### 3. 계획 확인과 적용

client를 지정하지 않으므로 앱 연결을 요구하지 않습니다. 먼저 dry-run으로 계획을 확인한 뒤 적용합니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

각 SDWT 아래에 `admin`, `user`, `viewer` 그룹을 생성합니다. 사용자 CSV를 지정하면 EPID를 기본 username으로 등록하고,
소속 SDWT·line을 저장하며, 본인 SDWT의 `user` 그룹에 가입시킵니다.
`admin`이나 다른 SDWT 권한은 자동 부여하지 않으며 관리자가 필요한 그룹 가입으로 지정합니다.

**실패 확인:** realm 기본 그룹에 의한 의도하지 않은 권한 부여, 중복 신원, 기존 그룹의 속성·역할 매핑이 발견되면 쓰기 전에 중단합니다. 사용자 등록 중 중단되면 완료된 행은 유지되므로 원인을 해결하고 재실행합니다.

### 4. 등록 확인

Admin Console의 `Groups`에서 `/{SDWT}/admin|user|viewer`를, `Users`에서 시험 사용자의 EPID·소속·그룹 가입을 확인합니다.
대량 등록 전에 시험 계정의 최초 사내 로그인·계정 연결을 확인합니다.

**다음 단계:** [설정 완료 확인](#설정-완료-확인). Portal client가 등록돼 있다면 [SDWT 공통 scope 연결](#sdwt-공통-scope-연결)도 수행합니다.

## 앱 연결

[설정 완료 확인](#설정-완료-확인)까지 마친 뒤 진행합니다.
앱마다 별도의 client ID·secret·callback·토큰·권한을 설정합니다. 사내 AD FS client와 앱 client는 서로 다릅니다.
Portal과 Headlamp는 서로의 설치를 요구하지 않으므로 사용할 앱부터 연결합니다.

### Portal

[Portal client 등록](../../portal/docs/01-install.md#keycloak-client-등록)에서 입력 작성 → client 등록 → Portal 배포를 진행합니다.
등록 도구는 Portal client, 사내 claim 16개·소속 claim 2개, 앱 역할 mapper, `groups`(전체 경로 배열)를 발급하는 `sdwt-groups` mapper를 준비합니다.

#### SDWT 공통 scope 연결

SDWT CSV와 [관리자 인증 입력](#2-관리자-인증-입력)이 준비되면 Portal client 등록 후 실행합니다. `portal`은 실제 Portal client ID로 맞추며 사용자 CSV는 전달하지 않습니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

**기대 결과:** client의 `sdwt-groups` mapper가 공통 `sdwt-access-v1` 기본 scope로 이전되고, 해당 client의 Access Token 수명이 300초가 됩니다. `groups` claim의 내용은 바뀌지 않습니다.
앱이 실제 자원의 SDWT와 그룹 등급을 검사하는지는 앱에서 확인합니다.

### Headlamp

[Headlamp 최초 설치 안내](../../headlamp/README.md)를 따릅니다. Keycloak의 Headlamp client 등록만으로는 Kubernetes에 접근할 수 없으며 API server의 OIDC 신뢰 설정과 RBAC까지 완료해야 합니다.
`headlamp-admins`는 클러스터 전체 관리 권한용 전용 그룹이며 SDWT 업무 그룹·Portal 권한이나 Portal 등록 명령을 사용하지 않습니다.

### Airflow

[Airflow SSO 등록 안내](../../airflow/docs/03-deploy.md#keycloak-로그인)를 따릅니다.
기존 realm에 전용 `airflow` client를 등록하며 기본 조회는 정상 로그인한 모두에게 허용합니다.
운영 담당자에게만 해당 client의 `User` 또는 `Admin`을 직접 부여합니다. Portal의 앱 역할·SDWT 그룹·조직 mapper는 Airflow 권한에 사용하지 않습니다.

### 앱별 완료 기준

| 앱 | 확인할 결과 |
| --- | --- |
| Portal | 사내 로그인·callback 성공, 새 토큰의 신원 claim, 필요한 소속·그룹과 앱의 접근 판정 |
| Headlamp | 브라우저 로그인 성공, 허용한 관리자의 접근 성공, 허용하지 않은 사용자의 접근 거부 |
| Airflow | Keycloak 로그인, 기본 Viewer, 명시적 User·Admin, 기존 Portal Basic API 호출 |
| 추가 OIDC 앱 | 전용 client·redirect URI·issuer/JWKS·필요한 claim·권한 판정 확인 |

새 client를 만드는 것만으로 Portal의 mapper가 다른 앱에 복제되지 않습니다. claim 이름·대소문자·자료형·발급 위치와 실제 값을 앱에서 확인합니다.

## 사용자 필드와 claim

```text
사내 AD FS claim → IdP mapper → Keycloak 사용자 필드 → 앱별 token mapper → 앱 토큰
```

커스텀 속성은 사내 claim 이름과 대소문자를 그대로 사용합니다. 발급 열은 Portal 등록 도구가 만드는 계약이며 다른 앱은 필요한 mapper를 별도로 설정합니다.

| AD FS 수신 claim | Keycloak 내부 저장 필드 | 앱에 발급하는 claim |
| --- | --- | --- |
| loginid | loginid | loginid |
| userid (EPID) | username (기본 속성) | userid |
| username | display_name | username |
| deptname | deptname | deptname |
| mail | email (기본 속성) | mail |
| givenname | firstName (기본 속성) | givenname |
| surname | lastName (기본 속성) | surname |
| grdName | grdName | grdName |
| sabun | sabun | sabun |
| username_en | username_en | username_en |
| deptid | deptid | deptid |
| grdname_en | grdname_en | grdname_en |
| busname | busname | busname |
| intcode | intcode | intcode |
| intname | intname | intname |
| employeetype | employeetype | employeetype |

Keycloak 기본 `username`은 EPID(`userid`)이고, 사내 사람 이름 `username`은 충돌을 피해 `display_name`에 저장합니다.
예: `userid=90000001`, `loginid=hong.gildong`, `username=홍길동`이면 `username=90000001`, `loginid=hong.gildong`, `display_name=홍길동`으로 저장합니다.

### User Profile 권한

정의 원본은 [account-user-profile.json](../k8s/claims/account-user-profile.json)입니다.
프로필 필드는 본인·관리자가 조회하고 관리자만 편집합니다. 미정의 속성 정책은 `ADMIN_EDIT`입니다.
비밀번호·권한·로그인 시각은 커스텀 프로필에 복제하지 않습니다.

### IdP mapper

[수신 스크립트](../k8s/claims/sync-oidc-claim-mappers.sh)는 일반 속성 15개와 EPID mapper 1개를 등록합니다.
`epid-username`은 `${CLAIM.userid}`를 기본 username에 저장하는 Username Template Importer이며 `target=LOCAL`, `syncMode=FORCE`를 사용합니다.
EPID는 유일하고 변하지 않으며 재사용되지 않는 식별자여야 하고 `Email as username`은 꺼야 합니다.
다른 수신 mapper도 `FORCE`를 사용하며, 사내 응답에 해당 claim이 있어야 값이 저장됩니다.

### 소속과 권한

- 소속: `user_sdwt_prod`는 실제 소속 SDWT, `line_id`는 해당 line입니다. 관리자 또는 최초 CSV 등록으로 채우며 사내 IdP에서 수신하지 않습니다.
- 접근 권한: `/{SDWT}/admin`, `/{SDWT}/user`, `/{SDWT}/viewer` 그룹으로 관리합니다. 소속이 바뀌어도 그룹을 자동으로 부여하지 않습니다.

### 앱 토큰 계약

Portal 도구는 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 단일 문자열로 발급하며, 값이 없으면 해당 claim을 생략합니다.
`groups`는 전체 경로의 문자열 배열입니다. Portal DB 필드 이름과 Keycloak claim 이름은 별개의 계약입니다.
일반 신원 claim 전체를 공유하는 공통 Client Scope는 없으며, `sdwt-access-v1`은 그룹 발급용 scope입니다.
Headlamp는 별도 client의 그룹 mapper와 Kubernetes 권한 계약을 사용합니다.
