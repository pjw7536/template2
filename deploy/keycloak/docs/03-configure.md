# Keycloak 로그인·그룹·앱 연결

[앱 안내](../README.md)

- [Realm과 사내 로그인](#realm과-사내-로그인)
- [SDWT 그룹·사용자](#sdwt-그룹사용자)
- [앱 연결](#앱-연결)

## Realm과 사내 로그인

서버 설치를 마친 뒤 Realm → 사내 IdP → User Profile → IdP mapper → 선택 SDWT 순서로 설정합니다.
Portal·Headlamp client는 이후 앱 연결 단계에서 만듭니다.
아래 명령은 하나씩 실행하고 성공을 확인한 뒤 다음 단계로 넘어갑니다.

### 실행 준비

서버 설치 때 사용한 저장소 루트의 Bash에서 실행합니다. 새 터미널이라면 저장소로 이동한 뒤
아래 context 선택을 다시 합니다. `NAME` 열의 실제 클러스터 이름을 입력합니다.

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p '설정할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get secret keycloak-runtime
```

`keycloak-runtime`의 관리자 계정은 서버 설치 때 준비한 계정입니다.
각 Make 명령이 해당 설정 Job을 생성하고, 완료될 때까지 최대 15분 기다립니다. Job을 별도로 apply할 필요는 없습니다.

### 1. Realm 준비

```bash
make keycloak-realm-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

Admin Console에 서버 설치 때 입력한 관리자 계정으로 접속하고 `etch` realm을 선택합니다.
서버 최초 import가 이미 `etch`를 만들었다면 이 명령은 존재 여부만 확인합니다.
이후 모든 관리 화면 설정은 `master`가 아닌 `etch`에서 확인합니다.

### 2. 사내 Identity Provider 생성

[환경변수 안내](01-prepare.md#사내-identity-provider용-값)에 따라
`deploy/keycloak/env/prod.env`의 사내 client ID·secret을 입력합니다.
AD FS의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`입니다.
운영 기본 주소의 등록값은 `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint`입니다.
AD FS에 이 주소가 등록되어 있어야 사내 로그인 결과를 Keycloak에서 받을 수 있습니다.

```bash
vi deploy/keycloak/env/prod.env
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$KEYCLOAK_KUBE_CONTEXT" --env deploy/keycloak/env/prod.env
```

검사가 통과한 뒤 적용합니다.

```bash
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Identity providers → oidc`에서 연결이 생성됐는지 확인합니다.
Discovery 해석·인증 방식은 [Discovery 참고](05-reference.md#oidc-discovery)에 설명합니다.

### 3. User Profile 등록

```bash
make keycloak-profile-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Realm settings → User profile`에서 `loginid`, `deptname`, `grdName`, `display_name`, `sabun` 등을 확인합니다.
사용자는 본인 필드를 조회할 수 있고 편집은 관리자만 가능합니다. 전체 필드 정의는 [매핑 참고](05-reference.md#사용자-필드와-claim)에 있습니다.

### 4. 사내 claim 수신 mapper 설정

`Realm settings`에서 `Email as username`이 꺼져 있는지 확인한 뒤 실행합니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Identity providers → oidc → Mappers`에서 일반 속성 mapper 15개와 `epid-username` 1개를 확인합니다.
mapper 생성만으로 사용자 값이 채워지지는 않습니다. 사내 로그인을 거쳐야 수신합니다.

### 5. 소속·SDWT 그룹 초기 설정

SDWT 권한을 사용할 경우 [SDWT 설정](#sdwt-그룹사용자)을 완료한 뒤 이 문서로 돌아옵니다.
그룹·사용자는 앱 client 없이 등록합니다. SDWT를 사용하지 않으면 이 단계는 생략합니다.

### 설정 완료 확인

Portal·Headlamp를 설치하기 전에 Keycloak 기본 Account Console로 사내 로그인을 확인합니다.
브라우저에서 아래 주소를 열고 사내 provider를 선택해 시험 계정으로 로그인합니다.

```text
<공개 Keycloak URL>/realms/etch/account/
```

Account Console 경로는 [Keycloak 공식 시작 안내](https://www.keycloak.org/getting-started/getting-started-kube)를 따릅니다.

| 확인 위치 | 완료 기준 |
| --- | --- |
| Account Console | 사내 인증을 거쳐 사용자 계정 화면에 도달 |
| Admin Console → Users → 시험 사용자 | 기본 username은 EPID, loginid·deptname·grdName 등 사내에서 제공한 값이 저장됨 |
| Users → 시험 사용자 → Identity provider links | 사내 `oidc` 연결 확인 |
| Groups / Users → Groups | SDWT 사용 시 준비한 그룹과 시험 사용자의 가입 확인 |

CSV로 사전 등록한 계정은 첫 사내 로그인에서 계정 연결 확인이 필요할 수 있습니다.
EPID가 같다는 이유만으로 자동 연결을 가정하지 않습니다. 시험 계정으로 연결이 완료되는지 확인합니다.

위 항목을 모두 확인하면 Keycloak 자체 준비가 끝납니다. 다음은 [앱 연결](#앱-연결)입니다.
앱의 토큰·로그인·권한 검증은 각 앱 연결 단계에서 수행합니다.

### Job 결과 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
read -r -p '로그를 확인할 Job 이름: ' KEYCLOAK_JOB_NAME
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs "job/$KEYCLOAK_JOB_NAME"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso describe job "$KEYCLOAK_JOB_NAME"
```

| 작업 | 실행 파일 | Job 이름 |
| --- | --- | --- |
| Realm | `scripts/00-create-realm.sh` | `keycloak-realm-setup` |
| IdP | `scripts/01-create-idp.sh` | `keycloak-oidc-setup` |
| User Profile | `scripts/02-register-user-profile.sh` | `keycloak-user-profile-setup` |
| IdP mapper | `scripts/03-sync-idp-mappers.sh` | `keycloak-idp-mappers-setup` |
| SDWT | `scripts/05-setup-sdwt.sh` | Job 없이 관리자 API 사용 |

실행 파일 이름의 숫자는 유지하지만, 이 문서의 제목 순서대로 진행합니다.
Job 실패 시 로그의 원인을 해결하기 전 다음 단계로 넘어가지 않습니다.

## SDWT 그룹·사용자

SDWT 권한을 사용하는 경우, Keycloak의 Realm·User Profile·IdP mapper를 준비한 뒤 실행합니다.
여기서는 그룹·사용자만 등록하므로 Portal·Headlamp client는 아직 필요하지 않습니다.
앱 토큰에 그룹을 포함하는 설정은 이후 앱 연결 단계에서 수행합니다.

실행은 관리자 API를 사용합니다. Kubernetes Job이나 runtime Secret을 자동으로 사용하지 않습니다.
실제 사용자 CSV와 인증정보는 Git에 넣지 않습니다.

### 1. 입력 파일

[SDWT 템플릿](../inputs/sdwts.template.csv)과 [사용자 템플릿](../inputs/users.template.csv)을 저장소 밖 작업 경로에 복사합니다.
UTF-8 CSV로 저장하고 EPID·사번은 텍스트로 입력해 선행 0을 유지합니다. 헤더만 있는 파일은 사용할 수 없습니다.

SDWT–line CSV의 필수 헤더는 다음과 같습니다. SDWT 이름은 유일해야 하며 `/`를 포함할 수 없습니다.

```csv
user_sdwt_prod,line_id
SDWT-A,LINE-1
SDWT-B,LINE-1
```

사용자 CSV의 필수 헤더는 `userid,user_sdwt_prod`입니다. `userid`는 EPID이고 소속이 없으면 SDWT 칸을 비웁니다.
선택 헤더는 `sabun,loginid,username,mail,deptname,grdname_en`입니다. 이름·저장 위치는 [필드 계약](05-reference.md#사용자-필드와-claim)을 따릅니다.

```csv
userid,user_sdwt_prod,sabun,loginid,username,mail
90000001,SDWT-A,100001,example.user,예시사용자,user@example.invalid
```

예시는 가상 데이터이므로 실제 값으로 바꿉니다.
Portal을 사용할 사용자는 `sabun`, `loginid`를 CSV에 포함하거나 사내 로그인에서 수신할 수 있어야 합니다.

사용자 사전 등록이 필요 없고 그룹만 준비한다면 사용자 CSV 경로는 비워 둡니다.

저장소 루트의 Bash에서 파일 경로를 입력하고 서버 접속 없이 검사합니다.

```bash
read -r -p 'SDWT CSV 절대 경로: ' KEYCLOAK_SDWTS_CSV
read -r -p '사용자 CSV 절대 경로 (그룹만 만들면 Enter): ' KEYCLOAK_USERS_CSV
export KEYCLOAK_SDWTS_CSV KEYCLOAK_USERS_CSV
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1
```

### 2. 연결과 인증

관리자 API에 접근할 수 있는 공개 Keycloak URL과 서버 설치 때 준비한 관리자 계정을 입력합니다.
URL은 realm 경로를 제외한 HTTPS 주소입니다. 비밀번호는 입력 중 표시되지 않습니다.

```bash
read -r -p 'Keycloak 관리 접속 URL: ' KEYCLOAK_ADMIN_URL
read -r -p '관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p '관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_REALM=master
export KEYCLOAK_TARGET_REALM=etch
```

관리자 인증 realm은 `master`, 설정 대상은 `etch`입니다.
사내 CA 파일이 필요한 경우 아래 경로를 추가합니다. API 접속 시 인증서 검증을 생략하지 않습니다.

```bash
read -r -p '관리 API를 신뢰할 CA PEM 절대 경로: ' KEYCLOAK_CA_FILE
export KEYCLOAK_CA_FILE
```

OS가 이미 인증서를 신뢰하면 CA 변수는 생략합니다.

서비스 계정을 사용하는 경우 `KEYCLOAK_ADMIN_CLIENT_ID`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `KEYCLOAK_ADMIN_REALM`으로 인증합니다.
client secret이 있으면 사용자 비밀번호보다 우선합니다.

### 3. 계획 확인과 적용

아래는 client를 지정하지 않으므로 앱 연결을 요구하지 않습니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

출력된 그룹·신규 사용자 건수를 확인한 뒤 적용합니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

각 SDWT 아래에 `admin`, `user`, `viewer` 그룹을 생성합니다.
사용자 CSV를 지정하면 다음 작업도 수행합니다.

- EPID를 기본 username으로 등록합니다.
- 소속 SDWT·line을 저장합니다.
- 본인 SDWT의 `user` 그룹에 가입시킵니다.

`admin`이나 다른 SDWT 권한은 자동 부여하지 않습니다. 사용자별 추가 권한은 관리자가 필요한 그룹 가입으로 지정합니다.

기본 realm 그룹에 의한 의도하지 않은 권한 부여나 중복 신원이 발견되면 검사가 중단됩니다.

client를 생략한 이 단계에서는 앱용 scope를 생성·연결하지 않습니다.
앱의 그룹 발급 설정은 [앱 연결](#sdwt-그룹을-portal에-전달하는-경우)에서 수행합니다.

### 4. 등록 확인

Admin Console의 `Groups`에서 `/{SDWT}/admin|user|viewer`를 확인하고,
`Users`에서 시험 사용자의 EPID·소속·그룹 가입을 확인합니다.

사전 등록과 사내 IdP 계정 연결은 별개입니다. 첫 사내 로그인에서 계정 확인 절차가 필요할 수 있으며
EPID가 같다는 이유만으로 자동 연결하지 않습니다. 대량 등록 전 시험 계정의 최초 로그인·연결을 확인합니다.

[Keycloak 설정 완료 확인](#설정-완료-확인)으로 돌아갑니다.

## 앱 연결

Keycloak Account Console의 사내 로그인과 사용자 정보 확인까지 완료한 뒤 진행합니다.
앱마다 별도의 client ID·secret·callback·토큰·권한을 설정합니다. 사내 AD FS client와 앱 client는 서로 다릅니다.
Portal과 Headlamp는 서로의 설치를 요구하지 않으므로 사용할 앱부터 연결합니다.

### Portal

[Portal client 등록 안내](../../portal/docs/01-install.md#keycloak-client-등록)에서 입력 파일 작성 → client 등록 → Portal API 설정을 진행합니다.
이 작업은 `scripts/04-setup-portal-client.sh`를 사용하지만 파일명 숫자가 전체 설치 순서를 뜻하지는 않습니다.
Portal client와 사내 claim 16개·소속 claim 2개, Portal 앱 역할·SDWT groups mapper를 등록합니다.

Portal API 배포는 [Portal 배포 안내](../../portal/README.md)를 따릅니다.

#### SDWT 그룹을 Portal에 전달하는 경우

[SDWT 설정](#sdwt-그룹사용자)에서 준비한 CSV 경로와 관리자 인증 환경변수를 사용합니다.
Portal client 등록 후 아래를 실행합니다. `portal`은 실제 Portal client ID로 맞춥니다.
사용자를 다시 등록하지 않으므로 사용자 CSV는 전달하지 않습니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

Portal client 등록 단계에서 이미 `groups`를 전체 경로 배열로 발급합니다. 위 선택 작업은 다음 설정을 추가합니다.

- `sdwt-access-v1` 기본 scope를 연결합니다.
- 선택한 client의 Access Token 수명을 300초로 설정합니다.

앱의 권한 판정은 별도로 확인합니다. 앱이 실제 자원의 SDWT와 그룹 등급을 검사해야 합니다.

### Headlamp

[Headlamp 최초 설치 안내](../../headlamp/README.md)의 준비 → TLS·CA → 전용 client·Secret → API server → 배포·검증 순서로 진행합니다.
Keycloak의 Headlamp client 등록만으로는 Kubernetes에 접근할 수 없습니다.
API server의 OIDC 신뢰 설정과 RBAC까지 완료해야 합니다.

Headlamp의 `headlamp-admins`는 클러스터 전체 관리 권한을 위한 전용 그룹입니다.
SDWT 업무 그룹이나 Portal용 권한을 대신 연결하지 않습니다.
Headlamp에는 Portal 전용 등록 명령을 사용하지 않습니다.

### Airflow

[Airflow SSO 등록 안내](../../airflow/docs/03-deploy.md#keycloak-로그인)를 따릅니다.
기존 realm에 전용 `airflow` client를 등록하며 기본 조회는 정상 로그인한 모두에게 허용합니다.
운영 담당자에게만 해당 client의 `User` 또는 `Admin`을 직접 부여합니다.
Portal의 앱 역할·SDWT 그룹·조직 mapper는 Airflow 권한에 사용하지 않습니다.

### 앱별 완료 기준

| 앱 | 확인할 결과 |
| --- | --- |
| Portal | 사내 로그인·callback 성공, 새 토큰의 신원 claim, 필요한 소속·그룹과 앱의 접근 판정 |
| Headlamp | 브라우저 로그인 성공, 허용한 관리자의 접근 성공, 허용하지 않은 사용자의 접근 거부 |
| Airflow | Keycloak 로그인, 기본 Viewer, 명시적 User·Admin, 기존 Portal Basic API 호출 |
| 추가 OIDC 앱 | 전용 client·redirect URI·issuer/JWKS·필요한 claim·권한 판정 확인 |

새 client를 만드는 것만으로 Portal의 mapper가 다른 앱에 복제되지는 않습니다.
claim 이름·대소문자·자료형·발급 위치와 실제 값을 앱에서 확인합니다.
