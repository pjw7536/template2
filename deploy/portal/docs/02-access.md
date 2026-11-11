# Portal 최초 권한 설정과 기존 권한 전환

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**목적:** 최초 운영자와 앱·데이터 권한을 Keycloak에서 부여하고 새 로그인으로 확인합니다.

**준비물:** [Migration·배포·검증](01-install.md#migration배포검증)과 [client 등록](01-install.md#keycloak-client-등록) 완료, Keycloak Admin Console 관리자 계정.

## Keycloak 권한과 새 DB 시작

Portal은 `resource_access.<client-id>.roles`만으로 앱 접근을 판단합니다.
부서·소속 정보는 권한을 부여하지 않습니다. 조직 정책은 Keycloak 그룹 가입과 역할 매핑으로 운영합니다.

1. 새 DB에 전체 migration을 적용하고 Portal client 등록 도구를 실행합니다.
2. Keycloak에서 최초 운영자에게 Portal client의 `portal-admin`을 지정합니다.
3. client 등록 도구는 `portal-members` 그룹에 `portal-all-apps`를 연결합니다.
   운영자는 조직 정책에 따라 내부 사용자를 이 그룹에 가입시킵니다. 사용자 자동 가입은 하지 않습니다.
   제한 사용자는 `<scope>-user`를 지정합니다. 실제 관리 기능에는 해당 `<scope>-admin`을 사용합니다.
4. 데이터는 별도로 `/{SDWT}/viewer|user|admin` 그룹을 지정합니다.
   각각 조회, 조회·수정, 조회·수정·삭제입니다. `portal-admin`만 전체 데이터에 접근합니다.
5. 내부 사용자·외부 제한 사용자로 로그인하여 앱과 데이터의 허용·거부를 확인합니다.

계정은 `userid`(EPID)로 연결하며 `sabun`, `loginid`도 필요합니다. 소속과 접근 권한은 별개입니다.
전체 SDWT/line 목록을 Portal에 사전 등록하지 않습니다. 사용자 목록은 실제 로그인한 사용자만 표시합니다.

권한은 로그인 세션별로 고정되어 다음 로그인부터 갱신됩니다.
ID Token 만료와 Portal 세션 만료는 다르며 세션은 `SESSION_COOKIE_AGE`까지 유지됩니다.

권한 요청은 메일·메신저로 받고 Keycloak에서 처리합니다. Portal 변경 API는 410을 반환합니다.

비상 Django 관리자 계정은 `manage.py createsuperuser`에서 EPID·사번을 명시하여 생성합니다.
자동 기본 관리자 생성과 업무 Basic 인증은 없습니다. 비상 계정은 업무 API를 우회하지 못합니다.

### 기존 부서 기반 권한에서 전환

부서 claim으로 앱 접근을 허용하던 DB·세션을 역할 기반으로 옮길 때 수행합니다.

1. Portal client 등록 명령을 실행하여 `portal-members` 그룹과 역할 연결을 준비합니다.
2. 기존 내부 사용자 중 전체 앱 사용 대상자를 EPID로 확인하여 그룹에 가입시킵니다. 부서 claim만으로 자동 가입하지 않습니다.
3. 새 로그인 토큰에 `resource_access.<client-id>.roles`의 `portal-all-apps`가 포함되는지 확인합니다.
4. API와 Web을 함께 반영하고 사용자는 재로그인합니다. 이전 세션의 `internal` 값은 더 이상 앱 접근을 허용하지 않습니다.
5. 외부 env 파일에서도 폐기한 `PORTAL_INTERNAL_DEPT_IDS`를 제거합니다.

그룹 탈퇴 시 사용자에게 직접 부여한 `portal-all-apps`나 다른 그룹에서 상속한 동일 역할도 확인합니다.
`portal-all-apps`는 앞으로 추가되는 활성 앱에도 적용되며, SDWT 데이터 권한은 별도로 지정합니다.
응답의 `hasAllAppsAccess`는 역할 기반 전체 앱 사용 여부입니다.

**다음 단계:** 운영 중 설정 변경은 [설정 변경 반영](03-operations.md#설정-변경-반영)을 따릅니다.
