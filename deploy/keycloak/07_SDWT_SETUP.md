# 07. SDWT 그룹·사용자 최초 등록

[전체 설치 순서](README.md) · 이전: [수신 mapper 설정](04_SETUP_FLOW.md#4-사내-claim-수신-mapper-설정)

SDWT 권한을 사용하는 경우, Keycloak의 Realm·User Profile·IdP mapper를 준비한 뒤 실행합니다.
**Portal·Headlamp client는 아직 필요하지 않습니다.** 여기서는 그룹·사용자만 등록하고 앱에 그룹을 발급하는 설정은 앱 연결 때 수행합니다.

실행은 관리자 API를 사용합니다. Kubernetes Job이나 runtime Secret을 자동으로 사용하지 않습니다.
실제 사용자 CSV와 인증정보는 Git에 넣지 않습니다.

## 1. 입력 파일

[SDWT 템플릿](inputs/sdwts.template.csv)과 [사용자 템플릿](inputs/users.template.csv)을 저장소 밖 작업 경로에 복사합니다.
UTF-8 CSV로 저장하고 EPID·사번은 텍스트로 입력해 선행 0을 유지합니다. 헤더만 있는 파일은 사용할 수 없습니다.

SDWT–line CSV의 필수 헤더는 다음과 같습니다. SDWT 이름은 유일해야 하며 `/`를 포함할 수 없습니다.

```csv
user_sdwt_prod,line_id
SDWT-A,LINE-1
SDWT-B,LINE-1
```

사용자 CSV의 필수 헤더는 `userid,user_sdwt_prod`입니다. `userid`는 EPID이고 소속이 없으면 SDWT 칸을 비웁니다.
선택 헤더는 `sabun,loginid,username,mail,deptname,grdname_en`입니다. 이름·저장 위치는 [필드 계약](06_CLAIMS.md)을 따릅니다.

```csv
userid,user_sdwt_prod,sabun,loginid,username,mail
90000001,SDWT-A,100001,example.user,예시사용자,user@example.invalid
```

예시는 가상 데이터입니다. 실제 값으로 작성합니다. Portal을 사용할 사용자는 `sabun`, `loginid`를 CSV에 포함하거나 사내 로그인에서 수신할 수 있어야 합니다.
사용자 사전 등록이 필요 없고 그룹만 준비한다면 사용자 CSV 경로는 비워 둡니다.

저장소 루트의 Bash에서 파일 경로를 입력하고 서버 접속 없이 검사합니다.

```bash
read -r -p 'SDWT CSV 절대 경로: ' KEYCLOAK_SDWTS_CSV
read -r -p '사용자 CSV 절대 경로 (그룹만 만들면 Enter): ' KEYCLOAK_USERS_CSV
export KEYCLOAK_SDWTS_CSV KEYCLOAK_USERS_CSV
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1
```

## 2. 연결과 인증

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
서비스 계정을 사용하는 경우 `KEYCLOAK_ADMIN_CLIENT_ID`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `KEYCLOAK_ADMIN_REALM`으로 인증하며 client secret이 있으면 사용자 비밀번호보다 우선합니다.

## 3. 계획 확인과 적용

아래는 client를 지정하지 않으므로 앱 연결을 요구하지 않습니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

출력된 그룹·신규 사용자 건수를 확인한 뒤 적용합니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

각 SDWT 아래에 `admin`, `user`, `viewer` 그룹을 생성합니다.
사용자 CSV를 지정하면 EPID를 기본 username으로 등록하고 소속 SDWT·line을 저장하며 본인 SDWT의 `user` 그룹에 가입시킵니다.
`admin`이나 다른 SDWT 권한은 자동 부여하지 않습니다. 사용자별 추가 권한은 관리자가 필요한 그룹 가입으로 지정합니다.
기본 realm 그룹에 의한 의도하지 않은 권한 부여나 중복 신원이 발견되면 검사가 중단됩니다.

client를 생략한 이 단계에서는 앱용 scope를 생성·연결하지 않습니다.
앱의 그룹 발급 설정은 [09 앱 연결](09_APP_CONNECTIONS.md#sdwt-그룹을-portal에-전달하는-경우)에서 수행합니다.

## 4. 등록 확인

Admin Console의 `Groups`에서 `/{SDWT}/admin|user|viewer`를 확인하고,
`Users`에서 시험 사용자의 EPID·소속·그룹 가입을 확인합니다.

사전 등록과 사내 IdP 계정 연결은 별개입니다. 첫 사내 로그인에서 계정 확인 절차가 필요할 수 있으며
EPID가 같다는 이유만으로 자동 연결하지 않습니다. 대량 등록 전 시험 계정의 최초 로그인·연결을 확인합니다.

[Keycloak 설정 완료 확인](04_SETUP_FLOW.md#설정-완료-확인)으로 돌아갑니다.
