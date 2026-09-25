# 06. 사용자 필드와 claim 매핑 참고

[시작 안내](README.md) · 실행: [2~4단계 설정](04_SETUP_FLOW.md) · 권한: [SDWT 초기 설정](07_SDWT_SETUP.md)

이 문서는 필드의 의미와 저장·발급 규칙을 확인할 때 사용합니다. 실행 명령은 단계별 설정 문서에 있습니다.

```text
AD FS claim → IdP mapper → Keycloak 사용자 필드 → client token mapper → Portal 토큰
                              ↑
                       User Profile 정의
```

User Profile은 필드와 편집 정책, IdP mapper는 로그인 시 수신 규칙, token mapper는 앱에 발급할 규칙입니다.
세 설정은 역할이 다르며 필드를 정의하는 것만으로 값이 채워지지 않습니다.

## 현재 구현: 발급 claim은 사내 이름 유지

현재 프로젝트의 token mapper는 **사내 claim 이름을 그대로 발급**합니다.
Keycloak 내부 저장 이름이나 Portal DB 필드 이름이 다르더라도 반환 claim 이름은 바뀌지 않습니다.

```text
사내 수신 claim       Keycloak 내부 저장       앱에 발급하는 claim
loginid          →   loginid             →   loginid
deptname         →   deptname          →   deptname
grdName          →   grdName            →   grdName
```

이 규칙은 [mapper 스크립트](k8s/claims/sync-oidc-claim-mappers.sh)의
`profile_attribute()`와 `sync_client_mapper()`에 구현돼 있습니다.
현재 4번 실행 경로는 Portal client에 사내 claim 16개와 소속 claim 2개를 등록합니다.
사내 claim 16개는 ID Token·Access Token·UserInfo에 단일 문자열(`String`, `multivalued=false`)로 설정됩니다.
필드 이름의 대소문자도 유지합니다. 예를 들어 `grdName`과 `grdname_en`은 서로 다른 claim입니다.

**커스텀 저장 필드도 사내 이름인 `loginid`, `deptname`, `grdName`으로 통일했습니다.**
기존 `knox_id`, `department`, `grd_name` 값은 아래 전환 절차로 복사하며 자동 삭제하지 않습니다.
이 문서는 저장소 구현을 설명하며 운영 서버의 Job 적용 여부와 실제 발급값은 별도로 확인해야 합니다.

## 사내 claim 수신 계약

3번 IdP mapper 단계는 기존 `oidc`의 접속 설정을 변경하지 않고 다음 16개 claim을 동기화합니다.
일반 속성 mapper 15개와
EPID를 기본 username으로 지정하는 `epid-username` mapper 1개를 사용합니다(총 16개).

```text
loginid userid sabun username username_en
givenname surname deptname deptid mail grdName grdname_en busname
intcode intname employeetype
```

2번 단계는 User Profile을 `k8s/claims/account-user-profile.json`으로 교체합니다. 기존 커스텀 정의를 합치지 않고
사내 claim 중심의 신원 필드에 맞춥니다. Keycloak 기본 `username`, `email`은 유지합니다.
성·이름은 기본 `firstName`, `lastName`을 사용하고 커스텀 `givenname`, `surname` 정의는 제거합니다.
프로필 필드는 `view: [admin, user]`로 설정하여 사용자가 계정 화면에서 본인 정보를
조회할 수 있게 합니다. 편집은 `edit: [admin]`으로 관리자만 허용합니다. 미정의 과거 속성은
`ADMIN_EDIT`로 관리합니다. 조회 권한 변경은 2번 프로필 단계 재실행으로 반영합니다.
비밀번호·권한·로그인 시각은 프로필에 복제하지 않습니다.
프로필·mapper Job 자체는 사용자 값을 복사하거나 삭제하지 않습니다. 기존 값 복사는 아래 별도 전환 도구로 실행합니다.

| AD FS 수신 claim | Keycloak 내부 저장 필드 | 앱에 발급하는 claim | Portal DB의 account_user 필드 |
| --- | --- | --- | --- |
| loginid | loginid | loginid | knox_id |
| userid (EPID) | username (기본 속성) | userid | avatarid |
| username | display_name | username | username |
| deptname | deptname | deptname | department |
| mail | email (기본 속성) | mail | email |
| givenname | firstName (기본 속성) | givenname | givenname |
| surname | lastName (기본 속성) | surname | surname |
| grdName | grdName | grdName | grd_name |
| sabun | sabun | sabun | sabun |
| username_en | username_en | username_en | username_en |
| deptid | deptid | deptid | deptid |
| grdname_en | grdname_en | grdname_en | grdname_en |
| busname | busname | busname | busname |
| intcode | intcode | intcode | intcode |
| intname | intname | intname | intname |
| employeetype | employeetype | employeetype | employeetype |

마지막 열은 Portal이 받은 값을 저장하는 DB 필드이며 Keycloak이 반환하는 claim 이름이 아닙니다.
다른 앱은 Portal DB 명칭을 알 필요 없이 세 번째 열의 claim을 사용합니다.

예를 들어 사내 `userid=90000001`, `loginid=hong.gildong`, `username=홍길동`이면
Keycloak 기본 `username=90000001`, `loginid=hong.gildong`,
`display_name=홍길동`으로 저장합니다. Portal token의 `username`은 계속 사람 이름인
`홍길동`이며 `userid`는 EPID입니다. 사내 `givenname`은 기본 `firstName`에, `surname`은
기본 `lastName`에 저장합니다. 기존 이름의 IdP mapper를 갱신하며 사내 재로그인 때 반영됩니다.
Portal token의 `givenname`·`surname`은 기본 property에서 읽어 기존 claim 이름으로 전달합니다.
과거 커스텀 속성값은 일괄 삭제하지 않으며 새 mapper에서 읽지 않습니다. 사내 응답에 없는 `first_name`·`last_name`은
수집·발급하지 않으며 기존 IdP·Portal client mapper도 각 Job 실행 시 제거합니다.
`username`을 성·이름으로 분리하지 않습니다. 기존 사용자 값과 공유 `profile` scope의
표준 mapper는 유지합니다. 기본 필드가 채워지면 `given_name`·`family_name`·`name`에도
해당 이름이 반영될 수 있습니다.
기본 필드의 프로필 정책은 [Keycloak User Profile 문서](https://www.keycloak.org/docs/latest/server_admin/#user-profile)를 참고합니다.

`epid-username`은 Username Template Importer(`oidc-username-idp-mapper`)이며
`template=${CLAIM.userid}`, `target=LOCAL`, `syncMode=FORCE`를 사용합니다. 사용자가 확인한
EPID의 유일성·불변성·재사용 금지를 전제로 하며 사내 로그인 응답에 `userid`가 있어야 합니다.
기존에 사내 IdP와 연결된 계정은 재로그인 때 같은 Keycloak 사용자 ID와 broker 연결을 유지한 채
username을 EPID로 갱신합니다. Job 자체가 모든 사용자 레코드를 일괄 변경하지는 않습니다.
`avatarid` 프로필 정의와 기존 IdP `userid` 속성 mapper는 제거합니다. EPID는 기본 username에만
저장하며 Portal token의 `userid`는 이 property를 읽습니다. 기존 avatarid 값은 일괄 삭제하지 않습니다.
Keycloak부터 정비하며 Django의 avatarid 컬럼과 프론트엔드는 후속 정비 대상으로 둡니다.
`loginid`, 사번과 사람 이름의 의미는 유지합니다. 기본 `profile` client scope를 쓰는
다른 앱은 `preferred_username`에서 EPID를 보게 될 수 있습니다.

realm의 `Email as username`이 켜져 있으면 EPID mapper가 무시될 수 있어 Job이 변경 전에
중단합니다. 해당 옵션을 확인하고, 기존에 수동 생성한 계정의 username이 다른 사람의 EPID와
충돌하지 않는지도 전환 전에 확인합니다. 사내 IdP의 broker ID 설정은 변경하지 않습니다.

Identity Provider mapper는 `FORCE`로 설정합니다. 사내 OIDC를 거쳐 로그인해야 새 속성이
채워지며, 프로필 정의를 등록하는 것만으로 외부에서 제공되지 않은 값이 생기지는 않습니다.
Portal token mapper는 단계별 설정의 4번 앱 client Job이 담당하며 기존 claim 이름을 유지합니다.

## 적용 방법과 확인

실행은 [단계별 설정](04_SETUP_FLOW.md)의 2번 User Profile → 3번 IdP mapper → 4번 Portal client 순서입니다.
각 단계의 전용 명령은 서로의 설정을 변경하지 않습니다. 기존 통합 claim Job은 프로필과 IdP mapper를 함께 적용하는 호환 경로입니다.

프로필을 바꾼 뒤에는 `Realm settings → User profile → Attributes`에서 정의를 확인합니다.
사내 재로그인 후 `Users → 사용자`에서 기본 username·email과 커스텀 속성값을 확인합니다.
기존 Keycloak 세션만 재사용하면 새 사내 정보가 반영되지 않을 수 있습니다.

## 기존 사용자 저장 이름 전환

신규 설치는 2 → 3 → 4번 순서로 진행합니다. 기존 사용자가 있다면 다음 순서로 전환합니다.

1. 로그인·사용자 편집을 잠시 중단하고 사용자 데이터를 백업합니다.
2. 2번 User Profile을 등록해 `loginid`, `deptname`, `grdName` 정의를 준비합니다.
3. [SDWT 도구의 연결과 인증](07_SDWT_SETUP.md#2-연결과-인증)과 같은 관리자 환경변수를 설정합니다.
4. 아래 dry-run으로 검사한 뒤 복사를 적용합니다.
5. 3번 IdP mapper와 4번 Portal client mapper를 적용합니다. 같은 속성을 읽는 다른 client mapper도 새 저장 이름으로 변경합니다.
6. 사내 재로그인으로 새 값을 수신하고 새 토큰의 claim을 확인한 뒤 로그인을 재개합니다.

```bash
make keycloak-claim-attributes-migrate
make keycloak-claim-attributes-migrate KEYCLOAK_CLAIM_MIGRATION_APPLY=1
```

[전환 도구](scripts/migrate_claim_attributes.py)는 `knox_id → loginid`,
`department → deptname`, `grd_name → grdName`만 복사합니다. 새 값이 비었을 때만 채우고,
두 값이 다르면 전체 사전 검사에서 중단합니다. 동일 값은 그대로 유지하며 재실행 가능합니다.
이전 속성·사용자 ID·broker 연결·그룹·Portal DB는 유지합니다. 예전 속성은 이후 사내 로그인으로 갱신되지 않으므로 새 mapper만 사용합니다.
사전 검사 후 동시 변경도 저장 직전에 확인하지만 API가 원자적인 비교·저장을 제공하는 방식은 아니므로 작업 중 사용자 편집을 멈춰야 합니다.
중간 실패 시 이미 완료한 사용자 복사는 유지됩니다. 원인을 해결하고 재실행합니다.

기본 필드 예외는 유지합니다. `userid → username`, `mail → email`,
`givenname → firstName`, `surname → lastName`이며, 사내 사람 이름 `username`은
기본 로그인 식별자와 충돌하므로 `display_name`에 저장합니다.

## Portal 토큰 발급과 API 연결

Portal 입력은 Git에서 추적하는 `deploy/portal/env/prod/api.env`에 작성합니다. client는
[Portal client 등록 절차](../portal/k8s/jobs/keycloak-client/README.md)로 별도 생성·갱신하며,
API Secret과 client 등록 작업이 같은 env 파일을 읽습니다.

```dotenv
OIDC_PROVIDER=keycloak
OIDC_CLIENT_ID=portal
OIDC_CLIENT_SECRET=<Portal 전용 client secret>
OIDC_ISSUER=https://etch-sso.samsungds.net/realms/etch
ADFS_AUTH_URL=https://etch-sso.samsungds.net/realms/etch/protocol/openid-connect/auth
ADFS_LOGOUT_URL=https://etch-sso.samsungds.net/realms/etch/protocol/openid-connect/logout
OIDC_REDIRECT_URI=https://<Portal DNS>/auth/keycloak/callback/
OIDC_TOKEN_URL=http://keycloak.etch-sso.svc.cluster.local:8080/realms/etch/protocol/openid-connect/token
OIDC_JWKS_URL=http://keycloak.etch-sso.svc.cluster.local:8080/realms/etch/protocol/openid-connect/certs
```

공개 issuer/DNS와 내부 token/JWKS URL을 서로 바꾸지 않습니다.

기존 `etch` realm은 초기 import에서 덮어쓰지 않으므로 등록된 사용자와 Portal client는
유지됩니다. 기존 클러스터를 새 구조로 바꿀 때 realm이나 PostgreSQL PVC를 삭제할 필요가 없습니다.

직급은 `grdName → grdName → grdName` 매핑을 복원하며 `grdname_en`도 유지합니다.
`origincomp`는 계속 프로필에서 제외하고 각 Job이 기존 mapper를 삭제합니다.
기존 사용자 속성값과 Django DB 컬럼은 일괄 삭제하지 않습니다.
직급 mapper 변경은 3번·4번을 재실행하고 사내 재로그인한 뒤 확인합니다. 프로필 정의도 바뀌었다면 2번을 먼저 실행합니다.

## 기존 사내 OIDC 앱을 연결할 때

현재 사내 claim 발급 mapper는 **client별로 등록**합니다. 새 client를 만드는 것만으로
Portal에 연결된 mapper가 자동 적용되지는 않습니다. 신규 앱에도 해당 mapper와 발급 위치를 설정해야 합니다.
4번 실행 파일은 Portal의 callback·PKCE·logout 계약을 함께 설정하므로 다른 앱용 범용 등록 파일로 사용하지 않습니다.

사내 claim 16개를 여러 client에 공유하는 공통 Client Scope는 아직 구현하지 않았습니다.
5번 SDWT 도구의 `sdwt-access-v1`은 `groups`용 scope이며 사내 신원 claim 전체를 공유하는 기능과 다릅니다.

앱 전환 시 다음을 확인합니다.

| 확인 대상 | 이유 |
| --- | --- |
| issuer·discovery·JWKS 및 client 등록 정보 | 앱이 새 Keycloak 발급자를 신뢰하고 토큰을 검증해야 함 |
| claim 이름·대소문자·자료형·실제 값 | 이름만 같아도 값의 의미나 배열/문자열 형식이 다르면 호환되지 않음 |
| ID Token·Access Token·UserInfo 중 앱이 읽는 위치 | 앱이 사용하는 응답에 필요한 claim이 포함돼야 함 |
| `sub`와 기존 사용자 식별 기준 | Keycloak의 `sub`가 이전 AD FS의 값과 같다고 가정하지 않음. EPID `userid`와도 구분 |
| redirect URI·scope·logout | 앱의 실제 로그인·로그아웃 설정과 맞아야 함 |

설정 후 시험 계정의 새 토큰과 사용자 연결을 확인합니다. claim 이름 유지가 앱의 무변경 전환 전체를 보장하지는 않습니다.

## 실제 소속 정보: user_sdwt_prod·line_id

`user_sdwt_prod`는 현재 소속 SDWT, `line_id`는 그 SDWT가 속한 line의 ID입니다.
두 필드는 선택적 단일 문자열로 User Profile에 정의하며 본인은 조회만, 관리자는 수정할 수 있습니다.
`Users → 사용자 → General`에서 확인·입력할 수 있습니다. 실제 값은 EPID 기준 참조 테이블을
사용하는 최초 일괄 등록 또는 관리자가 저장합니다. 이후 참조값으로 자동 덮어쓰지 않습니다.
필드 생성만으로 소속값이 채워지지 않습니다.
사내 OIDC에는 두 필드의 수신 mapper를 만들지 않으므로 사내 로그인으로 덮어쓰지 않습니다.

2번에서 프로필, 3번에서 IdP mapper, 4번에서 Portal client를 설정하면 기존 사내 claim 16개와
소속 claim 2개를 ID Token·Access Token·UserInfo에 같은 이름으로 전달합니다.
값이 없으면 해당 claim은 생략됩니다. 이미 발급한 토큰은 변경되지 않으므로 새 토큰으로 확인합니다.
이 두 값은 실제 소속이며 접근 가능한 SDWT 목록이나 관리자 권한이 아닙니다.
접근 권한은 별도 그룹으로 관리합니다. 소속 2개는 client mapper로, SDWT 그룹은 5번에서 연결하는 `sdwt-access-v1` 공통 scope로 발급합니다.

## 확정 설계: SDWT별 공통 권한

확정한 권한 구조는 `/{SDWT이름}/admin`, `/{SDWT이름}/user`, `/{SDWT이름}/viewer`입니다.
SDWT 아래 등급 하위 그룹에 사용자를 가입시키고, 이 계약을 사용하는 모든 업무 앱이 같은
SDWT 등급을 적용합니다. 앱별 그룹·업무 Client Role·Composite Role은 추가하지 않습니다.
소속 속성과 권한은 별개이며 최초 등록에만 본인 SDWT의 user 그룹에 가입시킵니다.
소속 변경·로그인 때 그룹을 자동 부여하지 않습니다. 신규 앱에도 기존 SDWT 등급이 적용됩니다.

그룹 전체 경로를 `groups` 문자열 배열로 전달하고 각 앱의 백엔드가 실제 자원 SDWT와
대조합니다. SDWT 관리자는 Keycloak·클러스터·앱 전역 관리자가 아닙니다.
Headlamp 등의 기존 시스템 관리 그룹은 유지합니다.

초기 설정은 [SDWT 그룹·사용자 초기 설정](07_SDWT_SETUP.md)의 `make keycloak-sdwt-init`으로 실행합니다.
사용자 CSV의 직급 입력은 사내 OIDC와 같은 이름의 선택 항목 `grdname_en`으로 저장합니다.
기존 사내 수신·토큰 발급 mapper를 사용하며 별도 `career_level` 속성은 추가하지 않습니다.
참조 CSV를 검사하고 그룹·공통 scope·선택 client·신규 사용자와 본인 SDWT user 가입을 준비합니다.
기본은 dry-run이며 기존 사용자 권한을 덮어쓰지 않습니다.

**Keycloak 초기 설정 도구는 구현했으며 운영 서버 실행과 Portal 권한 판정 전환은 별도입니다.**
초기 등록 도구만으로 앱의 그룹 권한 검사·세션 갱신이 구현되지는 않습니다.
Portal 세션 권한 갱신, 기존 권한 이관 및 검증 순서는
[SDWT 공통 권한 실행 계획](../../docs/agent/plans/keycloak-sdwt-group-authorization.md)을 따릅니다.
