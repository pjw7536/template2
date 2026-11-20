# Portal 최초 권한 설정

[Portal 가이드](../README.md)

설치·업데이트 절차는 [Portal 가이드](../README.md)에 있습니다. 이 문서는 최초 운영자와 앱·데이터 권한을 Keycloak에서 부여하고 새 로그인으로 확인하는 방법입니다.

**준비물:** [가이드 A](../README.md#a-최초-설치)의 배포 완료([client 등록](01-install.md#keycloak-client-등록) 포함), Keycloak 관리자 계정([Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api)).

## Keycloak 권한과 새 DB 시작

Keycloak의 역할·그룹 변경은 관리 화면이 아니라 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 수행합니다. 사용자 역할·그룹을 바꾸는 Make 타깃은 없으므로 그 절의 Admin REST API 호출 방법을 씁니다. realm은 `etch`, Portal client는 API env의 `OIDC_CLIENT_ID`(기본 `portal`)입니다.
로그인 확인은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 수행합니다.

Portal은 `resource_access.<client-id>.roles`만으로 앱 접근을 판단합니다.
부서·소속 정보는 권한을 부여하지 않습니다. 조직 정책은 Keycloak 그룹 가입과 역할 매핑으로 운영합니다.

1. [조회] 가이드 A의 배포가 새 DB에 전체 migration을 적용하고 Portal client를 등록했는지 확인합니다. [가이드 C](../README.md#c-배포-후-확인)의 `portal-migrate` Complete와 [client 등록](01-install.md#실행과-확인)의 Job 로그 끝 `portal-members 표준 그룹 준비 완료`로 확인합니다.
2. [변경] 최초 운영자 계정에 Portal client의 client 역할 `portal-admin`을 부여합니다. 최초 운영자의 Keycloak username은 요청에 주어지는 입력입니다. 요청에 없으면 부여하지 않고 보고의 남은 일에 적습니다.
   확인: 그 사용자의 Portal client 역할 매핑에 `portal-admin`이 있습니다.
3. [변경] 내부 사용자를 `portal-members` 그룹에 가입시킵니다. client 등록 도구가 이 그룹에 `portal-all-apps`를 연결해 두었습니다. 가입시킬 사용자는 조직 정책에 따라 요청에 주어지며 사용자 자동 가입은 하지 않습니다.
   제한 사용자는 그룹에 넣지 않고 `<scope>-user`를 지정합니다. 실제 관리 기능에는 해당 `<scope>-admin`을 사용합니다.
   확인: 가입시킨 사용자의 그룹 목록에 `/portal-members`가 있습니다.
4. [변경] 데이터는 별도로 `/{SDWT}/viewer|user|admin` 그룹을 지정합니다.
   각각 조회, 조회·수정, 조회·수정·삭제입니다. `portal-admin`만 전체 데이터에 접근합니다. SDWT 그룹과 사용자 소속을 CSV로 등록하는 도구는 [SDWT 그룹·사용자](../../keycloak/docs/02-configure.md#sdwt-그룹사용자)에 있습니다.
5. [조회] 내부 사용자·외부 제한 사용자로 로그인하여 앱과 데이터의 허용·거부를 확인합니다.

계정은 `userid`(EPID)로 연결하며 `sabun`, `loginid`도 필요합니다. 소속과 접근 권한은 별개입니다.
전체 SDWT/line 목록을 Portal에 사전 등록하지 않습니다. 사용자 목록은 실제 로그인한 사용자만 표시합니다.

권한은 로그인 세션별로 고정되어 다음 로그인부터 갱신됩니다.
ID Token 만료와 Portal 세션 만료는 다르며 세션은 `SESSION_COOKIE_AGE`까지 유지됩니다.

권한 요청은 메일·메신저로 받고 Keycloak에서 처리합니다. Portal 변경 API는 410을 반환합니다.

비상 Django 관리자 계정은 `manage.py createsuperuser`에서 EPID·사번을 명시하여 생성합니다.
자동 기본 관리자 생성과 업무 Basic 인증은 없습니다. 비상 계정은 업무 API를 우회하지 못합니다.

그룹 탈퇴 시 사용자에게 직접 부여한 `portal-all-apps`나 다른 그룹에서 상속한 동일 역할도 확인합니다.
`portal-all-apps`는 앞으로 추가되는 활성 앱에도 적용되며, SDWT 데이터 권한은 별도로 지정합니다.
응답의 `hasAllAppsAccess`는 역할 기반 전체 앱 사용 여부입니다.

운영 중 설정 변경은 [설정 변경 반영](03-operations.md#설정-변경-반영)을 따릅니다.
