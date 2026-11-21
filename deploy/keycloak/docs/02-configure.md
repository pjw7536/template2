# Keycloak 로그인·그룹·앱 연결

[Keycloak 가이드](../README.md)

설치·업데이트 절차는 [Keycloak 가이드](../README.md)에 있습니다. 이 문서는 설정 단계의 구조와 확인 방법, SDWT·역할 입력, 앱 연결, 사용자 필드와 claim 계약입니다.

- [Realm과 사내 로그인](#realm과-사내-로그인)
- [SDWT 그룹·사용자](#sdwt-그룹사용자)
- [소속별 역할](#소속별-역할)
- [앱 연결](#앱-연결)
- [앱 역할](#앱-역할)
- [사용자 필드와 claim](#사용자-필드와-claim)

## Realm과 사내 로그인

`make keycloak-setup`(`make ops-deploy APP=keycloak`의 한 단계)이 입력 검사 뒤 Realm → 사내 IdP → User Profile → IdP mapper를 순서대로 실행해 사내 로그인을 준비합니다.
각 단계는 설정 Job을 생성하고 완료될 때까지 최대 15분 기다립니다. Job을 별도로 apply하지 않습니다. 앱 client는 [앱 연결](#앱-연결)에서 만듭니다.

### 설정 단계와 Job

| 작업 | 단독 실행 Make 명령 | 실행 파일 | Job 이름 |
| --- | --- | --- | --- |
| Realm | `keycloak-realm-setup` | `scripts/00-create-realm.sh` | `keycloak-realm-setup` |
| IdP | `keycloak-idp-setup` | `scripts/01-create-idp.sh` | `keycloak-oidc-setup` |
| User Profile | `keycloak-profile-setup` | `scripts/02-register-user-profile.sh` | `keycloak-user-profile-setup` |
| IdP mapper | `keycloak-idp-mappers-setup` | `scripts/03-sync-idp-mappers.sh` | `keycloak-idp-mappers-setup` |
| Portal client | `keycloak-portal-client-setup` | `scripts/04-setup-portal-client.sh` | `portal-keycloak-client` |
| SDWT | `keycloak-sdwt-init` | `scripts/05-setup-sdwt.sh` | Job 없이 관리자 API 사용 |

위 네 단계는 `keycloak-setup`이 실행합니다. 소속 CSV를 지정하면 마지막에 SDWT도 등록합니다. Portal client는 Portal 배포가 등록합니다.

[변경] 한 단계만 다시 실행할 때는 그 단계의 Make 명령을 씁니다. 같은 명령을 다시 실행하면 기존 Job을 삭제하고 새로 만듭니다. IdP 단계에 다른 env 파일을 쓰면 `KEYCLOAK_ENV="<env 절대 경로>"`를 붙입니다.

```bash
make keycloak-profile-setup KUBE_CONTEXT="<context>"
```

성공: 명령 출력의 `설정 완료: profile`. 단계 이름은 `realm`, `idp`, `profile`, `mappers`입니다.

[조회] Job 결과를 확인합니다. 원인을 해결하기 전에는 다음 단계로 넘어가지 않습니다.

```bash
kubectl --context "<context>" -n etch-sso get jobs
kubectl --context "<context>" -n etch-sso logs job/<Job 이름>
kubectl --context "<context>" -n etch-sso describe job <Job 이름>
```

각 Job은 Keycloak 이미지의 `kcadm`으로 설정하고 로그 끝에 결과를 남깁니다. Job이 `Complete`이고 로그에 아래 문구가 있으면 그 단계는 끝난 것입니다.

| 작업 | Job 로그의 완료 문구 | 결과 |
| --- | --- | --- |
| Realm | `etch realm 생성 완료.` 또는 `etch realm 설정 반영 완료.` | [realm JSON](../k8s/server/etch-realm.json)으로 생성하거나 기존 realm에 선언된 속성을 반영 |
| IdP | `사내 OIDC 설정 완료. 기존 사용자와 realm은 유지됩니다.` | `Identity providers → oidc` 연결 생성·갱신 |
| User Profile | `User Profile 등록 완료. mapper는 별도 단계에서 실행하세요.` | `Realm settings → User profile`에 `loginid`, `deptname`, `grdName`, `display_name`, `sabun` 등 |
| IdP mapper | `사내 OIDC claim 16개의 동기화가 완료됐습니다. 대상: idp` | `Identity providers → oidc → Mappers`에 일반 속성 mapper 15개와 `epid-username` 1개 |

`결과` 열의 경로는 관리 화면(`etch` realm)에서의 위치입니다. 값까지 직접 대조해야 하면 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 조회합니다.

### 사내 IdP 사전 검사

[사내 IdP 입력](01-prepare.md#사내-identity-provider용-값)이 env에 있고 AD FS에 `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint`가 redirect URI로 등록되어 있어야 합니다. client 발급과 redirect URI 등록은 [AD FS](../../shared/docs/infrastructure/access.md#ad-fs) 절의 방법으로 합니다.
`keycloak-setup`은 IdP 등록 전에 아래 검사를 실행합니다.

[검사] 사전 검사만 따로 실행합니다. 다른 env 파일을 쓰면 `--env`에 같은 경로를 전달합니다.

```bash
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "<context>" --env deploy/keycloak/env/prod.env
```

성공: `사전 검사 통과`. 실패하면 `설정 중단: <원인>`이 출력되며 원인별 조치는 [가이드의 문제 해결](../README.md#문제-해결과-멈춤-조건)에 있습니다.

### Discovery 해석 규칙

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

### User Profile과 수신 mapper

필드 정의는 [사용자 필드와 claim](#사용자-필드와-claim)에 있습니다. 정의를 바꾸면 `make keycloak-profile-setup` 또는 가이드의 업데이트로 반영합니다.

IdP mapper Job은 EPID를 username으로 사용하기 위해 realm의 `Email as username`(`registrationEmailAsUsername`)을 자동으로 확인합니다. 켜져 있으면 해당 키만 끄고 다시 읽어 `false`일 때 mapper를 등록합니다. 이 단계의 성공 문구는 `realm의 Email as username 설정 반영 완료.`입니다. 확인이 실패하면 Job은 mapper 변경 전에 멈춥니다.

[변경] 기존 realm에 이 설정과 수신 mapper만 반영할 때 실행합니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="<context>"
```

`설정 완료: mappers`가 성공 기준입니다.

mapper 생성만으로 사용자 값이 채워지지 않으며 사내 로그인을 거쳐야 수신합니다.

### 설정 완료 확인

[조회] 관리 호스트에서 discovery 응답을 확인합니다. 관리 호스트가 사내 CA를 신뢰하지 않으면 `--cacert deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`([사내 CA 묶음](../../README.md#사내-ca-묶음))을 붙입니다.

```bash
curl -fsS https://sso.etch.samsungds.net/realms/etch/.well-known/openid-configuration
```

성공: JSON의 `issuer`가 `https://sso.etch.samsungds.net/realms/etch`입니다. `Could not resolve host`면 DNS 등록 전이며 `make keycloak-smoke KUBE_CONTEXT="<context>"`의 결과로 대신합니다.

사내 로그인은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다. 브라우저에서 `<공개 Keycloak URL>/realms/etch/account/`를 열고 사내 provider를 선택해 시험 계정으로 로그인하는 시나리오입니다. SDWT 권한을 사용하면 [SDWT 그룹·사용자](#sdwt-그룹사용자)를 완료한 뒤 확인합니다.

| 확인 위치 | 완료 기준 |
| --- | --- |
| Account Console | 사내 인증을 거쳐 사용자 계정 화면에 도달 |
| Admin Console → Users → 시험 사용자 | 기본 username은 EPID, loginid·deptname·grdName 등 사내에서 제공한 값이 저장됨 |
| Users → 시험 사용자 → Identity provider links | 사내 `oidc` 연결 확인 |
| Groups / Users → Groups | SDWT 사용 시 준비한 그룹과 시험 사용자의 가입 확인 |

Admin Console 행은 로그인한 시험 사용자의 저장값이며 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로도 조회할 수 있습니다.
CSV로 사전 등록한 계정은 첫 사내 로그인에서 계정 연결 확인이 필요할 수 있습니다. EPID가 같다는 이유만으로 자동 연결을 가정하지 않습니다.
시험 로그인을 확인하기 전에는 앱을 연결하지 않습니다. 앱의 토큰·로그인·권한 검증은 각 [앱 연결](#앱-연결) 단계에서 수행합니다.

## SDWT 그룹·사용자

소속 그룹 트리(팀 → 라인 → SDWT)와 선택적으로 사용자를 사전 등록합니다. 앱 client는 필요하지 않습니다. CSV 경로와 함께 [배포](../README.md#a-최초-설치)하거나 [별도 명령](../README.md#선택-sdwt-소속역할-관리-api)으로 적용합니다.

```text
/org
  /<팀>
    /<라인>
      /<SDWT>                 소속 그룹. 한 사람당 SDWT 하나에만 가입
```

같은 라인 이름이 여러 팀에 있을 수 있으므로 라인은 항상 `팀/라인`으로 구분합니다. SDWT 이름은 전체에서 유일합니다.
그룹 아래에 역할 그룹을 두지 않습니다. 등급(조회·일반·관리자)은 [소속별 역할](#소속별-역할)로 관리합니다.

준비물은 Realm·User Profile·IdP mapper 완료, 저장소 밖에 작성한 CSV, Keycloak 관리자 계정입니다.
관리자 API를 직접 사용하며 Kubernetes Job이나 runtime Secret을 사용하지 않습니다. 실제 사용자 CSV와 인증정보는 Git에 넣지 않습니다.

### 1. 입력 파일 검사

CSV의 내용(팀·라인·SDWT 목록과 사용자 소속)은 요청으로 받은 소속 데이터만 씁니다. 값을 추정하거나 예시 값을 쓰지 않습니다.

- CSV 파일로 받았으면 그 경로를 그대로 `KEYCLOAK_SDWTS_CSV`·`KEYCLOAK_USERS_CSV`에 씁니다.
- 표나 목록으로 받았으면 [변경] [SDWT 템플릿](../inputs/sdwts.template.csv)과 [사용자 템플릿](../inputs/users.template.csv)의 헤더에 맞춰 저장소 밖 경로에 CSV로 작성합니다. 위치는 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 앱 설정 폴더를 쓰고 권한은 0600으로 둡니다. 작성 뒤 아래 [검사] 명령으로 확인합니다.
- 요청에 소속 데이터가 없으면 SDWT 등록을 실행하지 않습니다.

UTF-8 CSV로 저장하고 EPID·사번은 텍스트로 입력해 선행 0을 유지합니다. 헤더만 있는 파일은 사용할 수 없습니다.

SDWT 목록 CSV의 필수 헤더는 `user_sdwt_prod,line_id,department`이며 `department`가 팀입니다. 팀은 사내 부서명(`deptname`)과 같은 값으로 씁니다.
팀·라인·SDWT 이름에는 `/`와 `:`(역할 이름 구분자)를 쓸 수 없고, SDWT 이름은 전체에서 유일해야 합니다.

```csv
user_sdwt_prod,line_id,department
SDWT-A,LINE-1,TEAM-1
SDWT-B,LINE-1,TEAM-1
SDWT-C,LINE-1,TEAM-2
```

사용자 CSV의 필수 헤더는 `userid,user_sdwt_prod`입니다. `userid`는 EPID이고 소속이 없으면 SDWT 칸을 비웁니다.
선택 헤더는 `sabun,loginid,username,mail,deptname,grdname_en`이며 저장 위치는 [사용자 필드와 claim](#사용자-필드와-claim)을 따릅니다.
Portal을 사용할 사용자는 `sabun`, `loginid`를 CSV에 포함하거나 사내 로그인에서 수신할 수 있어야 합니다.

```csv
userid,user_sdwt_prod,sabun,loginid,username,mail
90000001,SDWT-A,100001,example.user,예시사용자,user@example.invalid
```

예시는 가상 데이터입니다.

[검사] 저장소 루트에서 서버 접속 없이 검사합니다. CSV 경로는 명령마다 `KEYCLOAK_SDWTS_CSV`·`KEYCLOAK_USERS_CSV`로 전달하고, 그룹만 준비한다면 `KEYCLOAK_USERS_CSV=`로 비워 둡니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1
```

성공: `CSV 검증 완료: SDWT <n>개, 사용자 <n>명 (서버 연결 없음)`.

### 2. 관리자 인증 입력

`make keycloak-sdwt-init`·`keycloak-org-sync`·`keycloak-access-apply`는 `KEYCLOAK_ENV`(기본 `deploy/keycloak/env/prod.env`)의 `keycloak-public-url`·`bootstrap-admin-username`·`bootstrap-admin-password`를 관리자 접속 변수로 자동 전달합니다. 관리자 realm은 `master`가 기본이며, `deploy/shared/certs/<공개 host>/keycloak-ca-bundle.pem`([사내 CA 묶음](../../README.md#사내-ca-묶음))이 있으면 CA로 사용합니다.

다른 관리자 계정이나 주소를 쓸 때는 그 값이 든 env 파일을 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 방법으로 준비하고 각 Make 명령에 `KEYCLOAK_ENV="<env 절대 경로>"`를 붙입니다. 도구가 읽는 키는 `keycloak-public-url`(realm 경로를 제외한 공개 HTTPS 주소), `bootstrap-admin-username`, `bootstrap-admin-password`입니다. 비밀번호를 명령 줄에 쓰지 않습니다.

```text
make keycloak-org-sync KEYCLOAK_ENV="<env 절대 경로>"
```

도구가 읽는 환경변수입니다. 비밀값이 아닌 변수는 Make 명령 뒤에 `이름=값`으로 붙입니다.

| 환경변수 | 의미 | 기본값 |
| --- | --- | --- |
| `KEYCLOAK_ADMIN_URL`, `KEYCLOAK_ADMIN_USERNAME`, `KEYCLOAK_ADMIN_PASSWORD` | 관리자 접속 주소·계정·비밀번호 | `KEYCLOAK_ENV`의 값. 셋 중 하나라도 환경에 지정돼 있으면 env의 값을 채우지 않으므로 세 값이 모두 있어야 함 |
| `KEYCLOAK_ADMIN_REALM` | 관리자 계정이 속한 realm | `master` |
| `KEYCLOAK_TARGET_REALM` | 설정을 적용할 업무 realm | `etch` |
| `KEYCLOAK_CA_FILE` | 관리 API의 인증서를 검증할 CA PEM 절대 경로. 관리 호스트가 Keycloak 인증서를 신뢰하지 않고 CA 묶음도 없을 때 지정. 인증서 검증은 생략하지 않음 | CA 묶음이 있으면 그 파일 |
| `KEYCLOAK_ADMIN_CLIENT_ID`, `KEYCLOAK_ADMIN_CLIENT_SECRET` | 서비스 계정 인증. client secret이 사용자 비밀번호보다 우선하고, 이때도 env의 관리자 계정을 채우지 않으므로 `KEYCLOAK_ADMIN_URL`이 함께 있어야 함 | 비움(`admin-cli`와 관리자 계정 사용) |

### 3. 계획 확인과 적용

client를 지정하지 않으므로 앱 연결을 요구하지 않습니다. 먼저 dry-run으로 계획을 확인한 뒤 적용합니다.

[조회] dry-run:

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

성공: `계획:` 줄들과 `dry-run 완료. 서버 설정·사용자는 변경하지 않았습니다.`. `초기 설정 실패: …`로 끝나면 적용하지 않습니다.

[변경] 적용:

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

성공: `적용 완료. 기존 사용자·그룹 가입 관계는 변경하지 않았습니다.`와 `소속별 역할 반영 완료: …`.

`/org` 아래 없는 팀·라인·SDWT 그룹을 생성하고, 이어서 [소속별 역할](#소속별-역할) 반영을 함께 실행합니다.
이미 있는 그룹과 가입 관계는 바꾸지 않으므로 CSV에 행을 추가해 다시 실행하면 새 팀·라인·SDWT만 추가됩니다.
사용자 CSV를 지정하면 EPID를 기본 username으로 등록하고, 소속 SDWT·line과 팀을 `deptname`으로 저장하며, `/org/<팀>/<라인>/<SDWT>`에 가입시킵니다. 사용자 CSV의 `deptname`은 SDWT의 팀과 같아야 합니다.
관리자나 다른 SDWT 역할은 자동 부여하지 않으며 Etch Members에서 지정합니다.

실패: realm 기본 그룹에 의한 의도하지 않은 권한 부여, 중복 신원, 기존 그룹의 속성·역할 매핑이 발견되면 쓰기 전에 중단합니다.
SDWT가 CSV와 다른 위치(다른 팀·라인)에 이미 있어도 중단합니다. 이 경우들은 [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)이며 기존 그룹·사용자를 지우거나 옮기지 않습니다. SDWT의 위치를 바꾸는 방법은 Etch Members의 라인 이동이고, 옮긴 뒤 CSV를 같은 위치로 맞춥니다. 관리 화면에서 그룹을 직접 옮긴 realm은 `make keycloak-org-sync KEYCLOAK_ORG_APPLY=1`로 라인 역할을 맞춥니다. 사용자 등록 중 중단되면 완료된 행은 유지되므로 원인을 해결하고 재실행합니다.

### 4. 등록 확인

[조회] dry-run을 다시 실행해 남은 변경이 없는지 확인합니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
make keycloak-org-sync
```

성공: 첫 명령의 `계획: 소속 그룹 생성 - 팀 0개, 라인 0개, SDWT 0개`와 `신규 사용자 0명`, 둘째 명령의 `계획: 변경 없음`.

관리 화면에서 볼 때의 위치는 `Groups`의 `/org/{팀}/{라인}/{SDWT}`, `Clients` → `org` → `Roles`의 `sdwt:{SDWT}:viewer`·`user`·`admin`, `Users`의 시험 사용자 EPID·소속·그룹 가입입니다. 값을 직접 대조해야 하면 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 조회합니다.
대량 등록 전에 시험 계정의 최초 사내 로그인·계정 연결을 [설정 완료 확인](#설정-완료-확인)의 방법으로 확인합니다.

다음은 [설정 완료 확인](#설정-완료-확인)입니다. Portal client가 등록돼 있다면 [SDWT 공통 scope 연결](#sdwt-공통-scope-연결)도 수행합니다.

## 소속별 역할

소속 그룹 트리(`/org`)에 맞춰 SDWT별 등급 역할과 라인·팀 전체 역할, 토큰 claim(`affiliation`, `org_roles`)을 Keycloak에 맞춥니다.
권한 모델과 앱의 판단 규칙은 [Etch Members 문서](../../../apps/iam/README.md#권한-모델)에 있습니다.

| 반영 대상 | 내용 |
| --- | --- |
| client `org` | 역할 보관용 public client. 로그인에 쓰지 않습니다 |
| 역할 | `sdwt:{SDWT}:{등급}`, `team:{팀}:line:{라인}:{등급}`(그 라인 SDWT 역할 포함), `team:{팀}:{등급}`(그 팀 SDWT 역할 포함), 토큰 묶음 `org-all`(SDWT 역할만 포함. 토큰 `org_roles`에는 `sdwt:…` 값만 나감) |
| SDWT 그룹 | `sdwt:{SDWT}:user` 연결. 소속하면 자기 SDWT 일반 역할을 자동으로 받습니다 |
| client scope `org-claims` | `affiliation.team`·`line`·`sdwt`(속성 `deptname`·`line_id`·`user_sdwt_prod`)와 `org_roles` 발급. realm 기본 scope이며 카탈로그 앱 client에 연결합니다 |

[조회] dry-run으로 계획만 출력합니다. 관리자 인증은 [관리자 인증 입력](#2-관리자-인증-입력)과 같습니다.

```bash
make keycloak-org-sync
```

[변경] 적용:

```bash
make keycloak-org-sync KEYCLOAK_ORG_APPLY=1
```

성공: 다시 실행하면 `계획: 변경 없음`입니다. 라인·팀 역할의 하위 역할은 트리와 정확히 맞추므로 Admin Console에서 SDWT를 옮긴 뒤 실행하면 라인 역할도 바뀝니다.
경고: 트리에 없는 `org` 역할(삭제된 SDWT 등)은 지우지 않고 경고만 출력합니다. Etch Members의 SDWT 추가·라인 이동은 이 명령과 같은 결과를 바로 만듭니다.

## 앱 연결

[설정 완료 확인](#설정-완료-확인)까지 마친 뒤 진행합니다.
앱마다 별도의 client ID·secret·callback·토큰·권한을 설정합니다. 사내 AD FS client와 앱 client는 서로 다릅니다.
Portal과 Headlamp는 서로의 설치를 요구하지 않으므로 사용할 앱부터 연결합니다.

### Portal

Portal client는 `make ops-deploy APP=portal`의 `keycloak-portal-client-setup` 단계가 Portal `api.env`로 등록합니다. 입력과 등록 결과는 [Portal client 등록](../../portal/docs/01-install.md#keycloak-client-등록)에 있습니다.
등록 도구는 Portal client, 사내 claim 16개·소속 claim 2개, 앱 역할 mapper, `groups`(전체 경로 배열)를 발급하는 `sdwt-groups` mapper를 준비합니다.

#### SDWT 공통 scope 연결

SDWT CSV와 [관리자 인증 입력](#2-관리자-인증-입력)이 준비되면 Portal client 등록 후 실행합니다. `portal`은 실제 Portal client ID로 맞추며 사용자 CSV는 전달하지 않습니다.

[조회] dry-run:

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

[변경] 적용:

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

성공: `적용 완료`가 출력되고, dry-run을 다시 실행하면 `계획: 동일한 sdwt-groups client mapper 0개를 공통 scope로 이전`입니다. client의 `sdwt-groups` mapper가 공통 `sdwt-access-v1` 기본 scope로 이전되고, 해당 client의 Access Token 수명이 300초가 됩니다. `groups` claim의 내용은 바뀌지 않습니다.
앱이 실제 자원의 SDWT와 그룹 등급을 검사하는지는 앱에서 확인합니다.

### Headlamp

[Headlamp 가이드](../../headlamp/README.md)를 따릅니다. client와 관리자 그룹은 `make ops-deploy APP=headlamp`의 `headlamp-oidc-setup` 단계가 등록합니다. Keycloak의 Headlamp client 등록만으로는 Kubernetes에 접근할 수 없으며 API server의 OIDC 신뢰 설정과 RBAC까지 완료해야 합니다.
`headlamp-admins`는 클러스터 전체 관리 권한용 전용 그룹이며 SDWT 업무 그룹·Portal 권한이나 Portal 등록 명령을 사용하지 않습니다.

### Airflow

[Airflow SSO 등록 안내](../../airflow/docs/03-deploy.md#keycloak-로그인)를 따릅니다.
`make ops-deploy APP=airflow`의 `airflow-keycloak-client` 단계가 기존 realm에 전용 `airflow` client를 등록하며 기본 조회는 정상 로그인한 모두에게 허용합니다.
해당 client의 `User` 또는 `Admin`은 Airflow를 운영하는 사용자에게만 직접 부여합니다. Portal의 앱 역할·SDWT 그룹·조직 mapper는 Airflow 권한에 사용하지 않습니다.

### Etch Members

라인·SDWT 추가, 사용자 소속 변경, 앱 역할 부여는 [Etch Members](../../../apps/iam/README.md)에서 할 수 있습니다.
IAM의 Keycloak 설정과 앱 역할 카탈로그는 [Etch Members 배포](../../iam/README.md#a-최초-설치)가 적용합니다.

### 앱별 완료 기준

| 앱 | 확인할 결과 |
| --- | --- |
| Portal | 사내 로그인·callback 성공, 새 토큰의 신원 claim, 필요한 소속·그룹과 앱의 접근 판정 |
| Headlamp | 브라우저 로그인 성공, 허용한 관리자의 접근 성공, 허용하지 않은 사용자의 접근 거부 |
| Airflow | Keycloak 로그인, 기본 Viewer, 명시적 User·Admin, 기존 Portal Basic API 호출 |
| 추가 OIDC 앱 | 전용 client·redirect URI·issuer/JWKS·필요한 claim·권한 판정 확인 |

새 client를 만드는 것만으로 Portal의 mapper가 다른 앱에 복제되지 않습니다. claim 이름·대소문자·자료형·발급 위치와 실제 값을 앱에서 확인합니다.

## 앱 역할

[카탈로그](../access/catalog.json)에 적은 앱·기능의 역할, 포함 관계, realm 기본 역할을 Keycloak에 맞추고 Etch Members용 카탈로그를 저장합니다.
권한 모델과 앱의 판단 규칙은 [Etch Members 문서](../../../apps/iam/README.md#권한-모델)에 있습니다.

준비물은 대상 앱의 로그인 client(앱 배포에서 생성), `/iam` 그룹([Etch Members 가이드](../../iam/README.md#a-최초-설치)의 배포가 생성)이며 관리자 인증은 [관리자 인증 입력](#2-관리자-인증-입력)과 같습니다.

카탈로그 항목은 다음과 같습니다.

| 항목 | 값 | 만들어지는 역할 |
| --- | --- | --- |
| 단일 앱 `{ "client", "name", "default" }` | `default`: `open`·`closed` | `viewer` ⊂ `user` ⊂ `admin` |
| 기능이 여러 개인 앱 `{ "client", "name", "features": [...] }` | 기능마다 `key`·`name`·`default` | `<key>:viewer` ⊂ `<key>:user` ⊂ `<key>:admin`, 묶음 `all:viewer`·`all:user`·`all:admin` |
| 그룹 앱 `{ "group", "name", "infra" }` | Kubernetes처럼 그룹만 읽는 앱 | 없음(Etch Members 열만 생성) |

`open`인 앱·기능의 `viewer`는 realm 기본 역할에 들어가 모든 사용자가 받습니다. `closed`로 바꾸면 기본 역할에서 뺍니다.
SDWT별 데이터 범위는 앱 역할로 두지 않고 [소속별 역할](#소속별-역할)로 정합니다. Etch Members이 쓰도록 `org` client id도 카탈로그에 함께 저장하므로 `make keycloak-org-sync`를 먼저 실행합니다.

[검사] 서버 연결 없이 카탈로그만 검사합니다.

```bash
python3 deploy/keycloak/scripts/access_apply.py --validate-only
```

[조회] dry-run으로 계획만 출력합니다.

```bash
make keycloak-access-apply
```

[변경] 적용:

```bash
make keycloak-access-apply KEYCLOAK_ACCESS_APPLY=1
```

realm은 `KEYCLOAK_TARGET_REALM`(기본 `etch`)으로 바꿉니다.

성공: 계획 줄과 `적용 완료`가 출력되고, 다시 실행하면 `계획: 변경 없음`입니다. Etch Members를 새로고침하면 매트릭스에 앱 열이 보입니다.
경고: 카탈로그에 없는 역할·포함 관계는 지우지 않고 `경고:` 줄만 출력합니다. 경고는 적용을 막지 않으며 경고 줄을 보고에 남깁니다.
[승인] 앱이 새 역할로 전환된 뒤 이전 역할을 지우는 것은 되돌릴 수 없는 변경입니다. 삭제할 client와 역할 이름을 보여 주고 승인받은 뒤 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 삭제하고, `make keycloak-access-apply`의 `경고:` 줄에서 그 역할이 사라졌는지 확인합니다.
client가 없는 앱은 건너뛰며, `/iam` 그룹이 없으면 Etch Members용 카탈로그를 저장하지 않습니다.

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

### 로그인 사용자 표시 이름

Keycloak으로 로그인한 사용자의 화면 표시 기본값은 `display_name(loginid)`입니다. 새로 연동하는 앱도 사용자 메뉴와 프로필 요약에 이 형식을 사용합니다. 예를 들어 표시 이름이 홍길동이고 로그인 ID가 `hong.gildong`이면 `홍길동(hong.gildong)`으로 표시합니다. 하나만 있으면 그 값만 표시하고, 둘 다 없으면 앱의 기존 표시 동작을 따릅니다.

계정 식별에는 Keycloak의 기본 `username`(EPID)과 앱별 신원 식별자를 사용합니다. 권한 판단은 앱의 역할·그룹 설정을 따릅니다.

Etch Members와 Airflow는 ID Token으로 받은 두 속성을, Portal은 세션 API에 저장된 이름과 로그인 ID를 조합합니다. Headlamp용 ID Token에는 [배포된 표시용 mapper](../k8s/display-name/etch-display-name.js)가 만든 `etch_display_name`이 포함됩니다. Keycloak의 Preview 기능인 `scripts`로 이 mapper를 실행하며 `username`, `preferred_username`, `sub`, 그룹은 기존 방식으로 발급합니다. 표시용 mapper 원본을 갱신하면 [빌드 스크립트](../k8s/display-name/build.py)로 Kustomize가 마운트할 JAR를 다시 생성합니다.

### User Profile 권한

정의 원본은 [account-user-profile.json](../k8s/claims/account-user-profile.json)입니다.
Keycloak User Profile의 표시 라벨은 `display_name`, `loginid`, `original_deptname`처럼 각 속성의 실제 키를 그대로 씁니다. 기존 realm에 라벨을 반영할 때는 [설정 단계의 User Profile 명령](#설정-단계와-job)을 사용합니다. Etch Members에는 이름 `display_name`과 로그인 ID `loginid`를 각각 발급합니다.
프로필 필드는 본인·관리자가 조회하고 관리자만 편집합니다. 미정의 속성 정책은 `ADMIN_EDIT`입니다.
비밀번호·권한·로그인 시각은 커스텀 프로필에 복제하지 않습니다.

`job_title`은 IAM에서 관리자가 입력하는 직책(예: `PL`, `파트장`)입니다. PL은 현재 소속 라인의 대표, 파트장은 현재 소속 SDWT의 대표를 뜻합니다. 직급 `grdName`과 구분하는 단일 문자열 속성이며 최대 80자입니다. 빈 값이면 직책을 해제합니다. 사내 IdP 수신 mapper와 앱 발급 mapper에는 포함하지 않으며 권한 역할을 부여하지 않습니다. 정의 변경은 [User Profile 단계](#user-profile과-수신-mapper)로 반영합니다. 미정의 속성 정책 `ADMIN_EDIT`을 사용하는 기존 realm에서도 관리자 저장은 가능하지만 명시한 프로필 제한을 적용하려면 정의를 반영해야 합니다.

`original_deptname`은 파견자의 원소속 부서를 기록하는 선택 속성입니다. 관리자가 최대 128자의 부서명을 입력합니다. 사내 SSO가 수신한 현재 부서는 `deptname`에 저장합니다. 원소속 부서는 IAM과 Keycloak 사용자 프로필에서 조회하며 역할 판단용 claim과 앱 토큰에 발급하지 않습니다. [IAM 사용자 편집](../../../apps/iam/README.md#구성원-소속-이동)

### IdP mapper

[수신 스크립트](../k8s/claims/sync-oidc-claim-mappers.sh)는 일반 속성 15개와 EPID mapper 1개를 등록합니다.
`epid-username`은 `${CLAIM.userid}`를 기본 username에 저장하는 Username Template Importer이며 `target=LOCAL`, `syncMode=FORCE`를 사용합니다.
EPID는 유일하고 변하지 않으며 재사용되지 않는 식별자여야 하고 `Email as username`은 꺼야 합니다.
다른 수신 mapper도 `FORCE`를 사용하며, 사내 응답에 해당 claim이 있어야 값이 저장됩니다.

### 소속과 권한

- 소속: `user_sdwt_prod`는 실제 소속 SDWT, `line_id`는 해당 라인입니다. 관리자, Etch Members 또는 최초 CSV 등록으로 채우며 사내 IdP에서 수신하지 않습니다. 팀은 사내 부서 `deptname`(IdP 수신)과 같은 값입니다. 권한 판단에는 쓰지 않습니다.
- 소속 그룹: `/org/{팀}/{라인}/{SDWT}` 하나에 가입합니다. 속성과 그룹은 Etch Members의 소속 변경이 함께 바꾸며, 토큰에는 `affiliation: {team, line, sdwt}`로 나갑니다.
- 소속별 역할: client `org`의 `sdwt:{SDWT}:{등급}`, 라인 전체 `team:{팀}:line:{라인}:{등급}`, 팀 전체 `team:{팀}:{등급}`입니다. 등급은 `viewer`·`user`·`admin`입니다. 토큰에는 펼쳐진 목록 `org_roles`로 나갑니다. [소속별 역할](#소속별-역할)을 참고합니다.
- 앱 기능 권한: 앱 client 역할로 관리합니다. [앱 역할](#앱-역할)을 참고합니다.

### 앱 토큰 계약

Portal 도구는 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 단일 문자열로 발급하며, 값이 없으면 해당 claim을 생략합니다.
`groups`는 전체 경로의 문자열 배열입니다. Portal DB 필드 이름과 Keycloak claim 이름은 별개의 계약입니다.
일반 신원 claim 전체를 공유하는 공통 Client Scope는 없으며, `sdwt-access-v1`은 그룹 발급용 scope입니다.
Headlamp는 별도 client의 그룹 mapper와 Kubernetes 권한 계약을 사용합니다.
