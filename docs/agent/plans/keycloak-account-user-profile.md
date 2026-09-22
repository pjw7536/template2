# ExecPlan: account_user 기준 Keycloak 프로필

## 목표
- 사용자 합의대로 커스텀 User Profile을 account_user 신원 필드 기준으로 교체한다.
- 기본 username은 로그인 ID로 유지하며 사람 이름은 display_name → 토큰 username으로 연결한다.

## 현재 상태
- 기존 19개 mapper는 사내 claim 이름을 그대로 사용자 속성 이름으로 사용한다.
- 프로필 정의 없이 ADMIN_EDIT 정책만 등록하고 있다.

## 범위
- Keycloak 프로필 JSON, mapper, ConfigMap 및 전달 YAML, 문서·테스트.
- Django DB·API·권한, 기존 HTTPS 설정은 변경하지 않는다.

## 설계
- loginid→knox_id, userid→avatarid, username→display_name, deptname→department, mail→email, grdName→grd_name으로 저장한다.
- Portal token은 기존 19개 claim 이름을 유지하며 email·firstName·lastName은 기본 사용자 property mapper로 읽는다.
- 기본 username/email/firstName/lastName은 Keycloak 계약상 유지하고 커스텀 정의는 교체한다.
- 프로필 관리 권한은 admin만 편집하도록 한다. 기존 사용자 값의 일괄 이관은 하지 않고 사내 재로그인으로 채운다.
- 독립 mapper 전달 YAML에 필요한 ConfigMap을 함께 넣어 네트워크 스택 재적용을 피한다.

## 실행 단계
- [x] 프로필과 mapper 수정
- [x] 독립 배포와 안내 동기화
- [x] 회귀·실제 Keycloak 검증

## 검증
- make k8s-export / make k8s-render
- node --test scripts/tests/environment.test.cjs scripts/tests/k8s-routing.test.cjs
- 격리 Keycloak 26.7.1에서 프로필 PUT과 mapper 생성·갱신 확인
- npm run agent:audit:docs / git diff --check

## 위험과 대응
- 기존 커스텀 프로필 정의는 사용자 승인대로 교체한다. 설정 JSON과 저장된 사용자 값은 별개다.
- 두 mapper 작업 완료 후 사내 재로그인이 필요하다. 운영 서버에는 자동 적용하지 않는다.

## 진행 기록
- 2026-09-14: 사용자 승인과 공식 26.7.1 mapper 구현을 확인했다.

- 2026-09-14: 회귀 테스트 28개, Kustomize 6개 진입점, 문서 감사와 셸·공백 검사 통과.
- 2026-09-14: 외부 네트워크 없는 임시 Keycloak 26.7.1에서 프로필 PUT, 19개 IdP·19개 client mapper 생성과 재실행 갱신 성공. 예시 ID 토큰의 username=홍길동, loginid=hong.gildong, deptname·mail·sabun 전달과 사용자 기본 username=hong.gildong 유지 확인.
- 실제 사내 OIDC 재로그인과 운영 배포는 수행하지 않았다. 예시 토큰 검증은 실제 사내 broker 로그인 검증을 대체하지 않는다.

## 참고
- [Keycloak Admin CLI와 User Profile](https://www.keycloak.org/docs/latest/server_admin/index.html)
- [26.7.1 IdP 속성 mapper](https://github.com/keycloak/keycloak/blob/26.7.1/services/src/main/java/org/keycloak/broker/oidc/mappers/UserAttributeMapper.java)

- 2026-09-14: 사용자 후속 요청에 따라 first_name·last_name 커스텀 정의를 제거하고 사내 claim을 기본 firstName·lastName에 연결한다. Portal claim 이름은 유지하며 기존 사용자 커스텀 값은 일괄 삭제하지 않는다.
- 성·이름 전환 검증: 셸 문법, Kustomize 렌더링, 회귀 테스트 28개, 문서 감사와 공백 검사 통과. 이번 전환의 운영 사내 로그인은 확인 전이다.

- 후속 요청: grd_name(grdName)·origincomp 프로필과 mapper 제거. 다음 각 Job에서 폐기 mapper 삭제, grdname_en 유지. Django 컬럼과 과거 사용자 속성값 일괄 삭제는 제외한다. 현행 mapper는 17개이며 앞선 19개 검증 기록은 이전 구성의 기록이다.
- 필드 제거 검증: 회귀 테스트 29개(폐기 mapper 삭제 범위 포함), YAML 렌더링, 셸 문법, 문서 감사와 공백 검사 통과. 운영 적용은 하지 않았다.
