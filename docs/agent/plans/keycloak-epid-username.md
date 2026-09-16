# ExecPlan: EPID를 Keycloak username으로 사용

## 목표
- 사내 OIDC userid의 EPID를 Keycloak 기본 username으로 사용한다.
- 기존 연결 사용자는 사내 재로그인 때 갱신하고 Portal의 사람 이름·사번 계약은 유지한다.

## 현재 상태
- 사용자가 EPID의 유일성·불변성·재사용 금지를 확인했다.
- 17개 속성 mapper가 userid를 avatarid로, username을 display_name으로 저장한다.
- Keycloak 26.7.1 Username Template Importer는 LOCAL/FORCE 설정으로 기존 연결 사용자의 username도 갱신한다.

## 범위
- IdP mapper 스크립트·프로필 표시명, 생성 YAML, 관련 문서와 테스트.
- Django DB/권한, Portal token mapper, HTTPS, 기존 계정의 일괄 재생성은 제외한다.

## 설계
- epid-username 이름의 oidc-username-idp-mapper를 생성·갱신한다.
- template은 ${CLAIM.userid}, target은 LOCAL, syncMode는 FORCE로 설정한다.
- BROKER_ID와 BROKER_USERNAME을 변경하지 않아 외부 연결 식별자를 유지한다.
- email-as-username 설정이 켜져 있으면 무시된 mapper를 성공으로 보고하지 않고 사전 검사에서 중단한다.
- client 전용 실행은 username mapper와 realm 설정을 변경하지 않는다.
- 초기 생성 및 기존 연결 사용자 재로그인, idempotent 갱신과 기존 token 호환을 검증한다.

## 실행 단계
- [x] IdP mapper와 프로필 표시명 구현
- [x] 문서와 생성 YAML 동기화
- [x] 회귀와 실제 Keycloak 검증

## 검증
- make k8s-export / make k8s-render
- node --test scripts/tests/environment.test.cjs scripts/tests/k8s-routing.test.cjs
- 격리 Keycloak 26.7.1에서 mapper와 로그인 동작 확인
- 셸 문법, 문서 감사, git diff --check

## 위험과 대응
- 로그인 시 EPID claim이 제공돼야 한다. 수동 생성 계정과 username 충돌은 운영 적용 전 확인한다.
- Keycloak 기존 세션 재사용만으로 갱신되지 않으므로 사내 OIDC를 거친 재로그인이 필요하다.
- 실제 사내 서버에는 자동 적용하지 않는다.

## 진행 기록
- 2026-09-14: 사용자 확인과 26.7.1 공식 UsernameTemplateMapper 구현을 기준으로 착수했다.

## 참고
- https://github.com/keycloak/keycloak/blob/26.7.1/services/src/main/java/org/keycloak/broker/oidc/mappers/UsernameTemplateMapper.java

- 회귀 테스트 33개, Kustomize 6개 진입점, 문서 감사, 셸 문법과 공백 검사 통과. 외부 통신이 없는 임시 Docker 네트워크에서 사내 IdP를 모사한 별도 realm과 기존 broker 연결 계정의 로그인 검증을 진행한다.

- 실제 Keycloak 26.7.1 검증 완료: corp realm을 OIDC 공급자로 연결하고 etch realm에서 authorization code 로그인·토큰 교환 수행. 기존 legacy.login 계정은 EPID 90000001로 갱신되면서 user ID/sub 및 federated identity userId를 유지했다. 신규 사용자는 EPID 90000002로 생성됐다.
- 두 로그인에서 avatarid, display_name, 기본 firstName/lastName과 Portal token의 userid/loginid/username/first_name/last_name 전달을 검증했다. 사용한 값은 테스트 전용이다.
- 실제 사내 OIDC와 운영 Kubernetes에는 적용하지 않았다. 임시 검증 컨테이너·네트워크는 종료한다.
