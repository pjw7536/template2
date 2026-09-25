# SDWT 그룹·사용자 초기 설정

`make keycloak-sdwt-init`으로 기존 Keycloak에 SDWT별 `admin/user/viewer` 하위 그룹을 만들고,
선택한 업무 client에 공통 그룹 claim을 연결합니다. 사용자 CSV도 지정하면 신규 계정의
소속과 본인 SDWT `user` 가입을 함께 등록합니다. 별도 Python 패키지 없이 Python 3.10+로 실행합니다.

기본은 **dry-run**입니다. `KEYCLOAK_SDWT_APPLY=1`에서만 관리 설정·사용자를 변경합니다.
실제 사용자 CSV와 인증정보는 Git에 넣지 않습니다. 서버 선택 checkout에서도 Portal 소스·local 없이 실행됩니다.

## 1. 입력 파일

작성용 빈 템플릿은 [sdwts.template.csv](examples/sdwts.template.csv)와
[users.template.csv](examples/users.template.csv)입니다. 별도 작업 경로에 복사한 뒤
첫 행의 헤더를 유지하고 둘째 행부터 실제 값을 입력합니다. 헤더만 있는 파일은 등록 입력으로
사용할 수 없습니다. UTF-8 CSV로 저장하고 EPID·사번은 텍스트로 입력해 선행 0을 유지합니다.

SDWT–line CSV는 다음 헤더를 사용합니다. SDWT 이름은 전역 유일하며 `/`를 포함할 수 없습니다.
서로 다른 SDWT가 같은 line에 속하는 것은 허용합니다.

```csv
user_sdwt_prod,line_id
SDWT-A,LINE-1
SDWT-B,LINE-1
```

사용자 CSV의 필수 헤더는 `userid,user_sdwt_prod`입니다. `userid`는 사내 EPID이며 소속이 없으면 SDWT 칸을 비웁니다.
선택 헤더는 `sabun,loginid,username,mail,deptname,grdname_en`입니다.
신원 컬럼은 사내 OIDC claim 이름을 그대로 사용합니다. 등록 시 `userid→username`,
`loginid→knox_id`, `username→display_name`, `mail→email`, `deptname→department`로
기존 Keycloak 저장 구조에 맞춥니다. `sabun`과 `grdname_en`은 같은 이름의 속성에 저장합니다.
`grdname_en`은 사내 OIDC의 동명 claim 값이며 같은 이름의 Keycloak 사용자 속성에 저장합니다.
빈 값은 생략하고 기존 사용자 값은 재등록으로 변경하지 않습니다. 이후 사내 로그인에서는
기존 `grdname_en` mapper로 갱신됩니다. CSV의 이전 `grd_name`, `career_level` 헤더는 사용하지 않습니다.
`username`은 사람의 표시 이름이며,
Keycloak 기본 username은 EPID가 됩니다. 실제 입력 예시는 [sdwts.csv](examples/sdwts.csv),
[users.csv](examples/users.csv)를 참고합니다. 예시는 가상 데이터이므로 운영 사용자로 등록하지 않습니다.

```csv
userid,user_sdwt_prod
90000001,SDWT-A
90000002,
```

Portal은 현재 로그인에 사번과 Knox ID를 요구하므로 Portal 사용자의 입력에는 `sabun`,
`loginid`도 포함하거나 사내 로그인에서 해당 신원 claim이 제공되어야 합니다.
중복 EPID·사번·Knox ID·이메일, 미등록 SDWT, 빈 line, 중복 SDWT, 열 수 오류는 등록 전에 차단합니다.
공백 제거·이름 치환·숫자 변환으로 다른 사용자를 합치지 않으며 EPID의 선행 0을 보존합니다.

서버에 접속하지 않고 입력만 검사할 수 있습니다.

```bash
make keycloak-sdwt-init \
  KEYCLOAK_SDWTS_CSV=/absolute/path/sdwts.csv \
  KEYCLOAK_USERS_CSV=/absolute/path/users.csv \
  KEYCLOAK_SDWT_VALIDATE_ONLY=1
```

## 2. 연결과 인증

업무 realm과 로그인 client는 먼저 준비합니다. 이 스크립트는 client secret·callback·사내
Identity Provider 설정을 생성하거나 변경하지 않습니다. 기존 [Keycloak 배포 절차](README.md)와
[Portal client 등록](../portal/k8s/jobs/keycloak-client/README.md)을 사용합니다.

아래 값은 실제 서버에 맞춰 환경변수로 입력합니다. 인증정보를 Make 인자나 스크립트 인자로 전달하지 않습니다.

```bash
read -r -p 'Keycloak 관리 접속 URL: ' KEYCLOAK_ADMIN_URL
read -r -p '관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p '관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD
export KEYCLOAK_TARGET_REALM=etch
```

- 관리자 인증 realm은 기본 `master`이며 `KEYCLOAK_ADMIN_REALM`으로 변경할 수 있습니다. 작업 대상에 `master`를 지정하는 것은 차단합니다.
- 서비스 계정은 `KEYCLOAK_ADMIN_CLIENT_ID`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `KEYCLOAK_ADMIN_REALM`을 지정합니다. client secret이 있으면 client credentials 방식을 사용합니다.
- 필요한 관리 작업은 대상 realm의 사용자·그룹 조회/관리, User Profile 관리, client/scope 조회/관리입니다. 앱의 SDWT admin은 이 운영 권한과 다릅니다.
- HTTPS 인증서를 검증합니다. 사내 CA는 `KEYCLOAK_CA_FILE` 경로로 지정합니다. HTTP는 loopback 주소만 허용하며 TLS 검증 생략 옵션은 없습니다.
- Kubernetes port-forward를 사용하면 별도 터미널에서 명시한 context의 Keycloak service를 로컬 포트에 연결하고 `http://127.0.0.1:<port>`를 관리 URL로 지정할 수 있습니다. 스크립트가 kubectl context를 바꾸지는 않습니다.
- 관리자 토큰은 메모리에만 보관하고 만료 전에 재발급합니다. 서버 오류 본문·사용자 행 내용·토큰·비밀번호는 출력하지 않습니다.

## 3. 계획 확인과 적용

```bash
# 기존 서버 설정·계정과 비교합니다. 변경하지 않습니다.
make keycloak-sdwt-init \
  KEYCLOAK_SDWTS_CSV=/absolute/path/sdwts.csv \
  KEYCLOAK_USERS_CSV=/absolute/path/users.csv \
  KEYCLOAK_SDWT_CLIENTS=portal

# 검토한 입력을 적용합니다.
make keycloak-sdwt-init \
  KEYCLOAK_SDWTS_CSV=/absolute/path/sdwts.csv \
  KEYCLOAK_USERS_CSV=/absolute/path/users.csv \
  KEYCLOAK_SDWT_CLIENTS=portal \
  KEYCLOAK_SDWT_APPLY=1
```

client는 쉼표로 여러 개 지정할 수 있습니다. 사용자를 등록하지 않으려면 `KEYCLOAK_USERS_CSV`를
생략합니다. client를 생략하면 그룹·프로필·사용자만 준비하고 앱 scope는 변경하지 않습니다.
환경변수 대신 직접 실행할 경우 `python3 deploy/keycloak/scripts/init_sdwt.py --help`를 참고합니다.

적용 작업은 다음으로 제한됩니다.

1. 사용자 프로필에 없는 등록용 관리 속성을 추가합니다. 다른 속성 정의는 보존하며, 기존 필드의 편집 권한·타입이 다르면 사전 검사에서 중단합니다.
2. CSV에 나온 SDWT의 부모와 `admin/user/viewer` 하위 그룹 중 없는 것만 만듭니다. 기존 그룹명·가입자는 바꾸지 않습니다.
3. 지정한 client에만 `sdwt-access-v1` default scope를 연결합니다. `groups`는 전체 경로 문자열 배열로 ID Token·Access Token·UserInfo에 발급합니다. 같은 정의의 `sdwt-groups` client mapper가 있으면 공통 scope 연결 후 해당 mapper만 제거합니다.
4. 지정한 client에 없는 `userid`, `user_sdwt_prod`, `line_id` mapper를 기존 계약대로 추가하고 Access Token 수명을 300초로 설정합니다. 다른 client 속성·scope·secret은 유지합니다.
5. 기본 선택 scope인 `microprofile-jwt`의 realm role `groups` mapper와 충돌하는 경우 선택한 client에서 해당 optional scope 연결만 해제합니다. scope 자체와 다른 client의 연결은 보존합니다. 그 외 groups 충돌은 자동 덮어쓰지 않고 중단합니다.
6. 신규 사용자를 EPID username으로 등록합니다. 소속이 있으면 같은 생성 요청에 소속 속성과 `/{SDWT}/user` 가입을 포함합니다. 비밀번호·관리자 등급·임의의 broker 연결은 생성하지 않습니다.

realm 기본 그룹이 있는 환경에서 사용자 등록을 시도하면 중단합니다. 기본 그룹으로 예기치 않은
추가 권한이 붙을 수 있으므로 해당 정책을 먼저 검토해야 합니다. 기존 SDWT 그룹에 속성·역할
매핑이 있어도 자동 제거하지 않고 중단합니다.

전체 목록을 사전 검사하지만 관리 API 작업 전체가 하나의 트랜잭션인 것은 아닙니다.
한 번에 한 운영자가 실행하고, 실행 중에는 다른 관리자의 그룹·계정 편집을 피합니다.
실패하면 원인을 해결한 뒤 같은 입력으로 재실행합니다. 완료된 설정·계정은 유지되고 누락된
설정·신규 계정부터 이어집니다. 응답이 유실돼도 기존 계정의 권한을 다시 부여하지 않습니다.

## 4. 기존 사용자와 첫 로그인

기존 EPID 계정은 소속·이메일·권한을 바꾸지 않고 건너뜁니다. 따라서 관리자에 의한 소속 변경이나
권한 회수를 재실행으로 되돌리지 않습니다. 다른 EPID 계정과 사번·Knox ID·이메일이 충돌하면
전체 사전 검사에서 중단합니다. 기존 사용자의 권한 이관은 이 초기 등록 명령의 기능이 아닙니다.

**사전 등록과 사내 IdP 계정 연결은 별개입니다.** Keycloak의 기본 first broker login flow에서는
기존 계정 확인이 필요할 수 있습니다. EPID username이 일치한다는 이유로 이 스크립트가
첫 로그인 확인을 우회하거나 이메일 기반 자동 연결 flow를 활성화하지 않습니다.
기존 사내 EPID mapper와 broker의 실제 사용자 식별자·계정 연결 정책을 시험 계정으로 검증한 뒤
대량 등록합니다. 사내 로그인 연결이 검증되지 않은 상태는 사용자 온보딩 완료가 아닙니다.

작업 후에는 생성한 그룹과 시험 계정의 속성·가입을 Admin Console에서 확인하고 새 토큰으로
claim을 검사합니다. 이전 토큰에는 이전 권한이 남으며 그룹 변경만으로 즉시 무효화되지 않습니다.

## 5. 검증과 현재 적용 범위

```bash
make keycloak-sdwt-test
make k8s-render-local
```

실제 Keycloak 통합 테스트는 전용 테스트 서버의 URL을 `KEYCLOAK_SDWT_TEST_URL`에 지정하고
관리자 환경변수를 설정한 뒤 `make keycloak-sdwt-test`를 실행합니다. 임의 이름의 `sdwt-test-*`
realm을 생성·삭제하므로 개발용 서버를 사용합니다. 운영 realm의 데이터를 사용하지 않습니다.

로컬 realm import에는 공통 정의와 같은 `sdwt-groups` mapper와 300초 client 설정을 포함합니다.
realm의 기본 profile/email scope 생성을 유지하기 위해 import에서는 client mapper로 두고,
초기 설정 스크립트를 실행하면 동일 계약의 공통 scope로 이전합니다. 기존 realm은 import로
덮어쓰지 않으므로 기존 로컬 DB에는 이 도구를 `KEYCLOAK_TARGET_REALM=portal`로 실행합니다.

이 스크립트는 Keycloak 초기 설정을 구현합니다. Portal의 그룹 기반 권한 판정·세션 갱신과
기존 앱별 권한 이관은 [실행 계획](../../docs/agent/plans/keycloak-sdwt-group-authorization.md)의
후속 단계입니다. 이 도구를 실행한 것만으로 모든 앱의 권한 전환이나 5분 이내 회수가 완료되지는 않습니다.
