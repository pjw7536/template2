# ExecPlan: Keycloak 실제 소속 속성 추가

## 목표
- user_sdwt_prod와 line_id를 실제 소속 사용자 속성 및 출력 claim으로 추가한다.

## 현재 상태
- 사내 claim mapper는 16개 항목을 수신·발급한다.
- 소속은 사내 OIDC가 아닌 EPID 기준 참조 테이블에서 제공한다.
- 전체 사내 속성 표준화와 Portal 권한 전환은 별도 작업이며 이 소속 claim 추가와 구분한다.

## 범위
- User Profile, 출력 mapper, 로컬 Keycloak 출력 계약, 배포 문서와 회귀 검사.
- 참조 테이블 접속·일괄 등록, 그룹 자동 가입, Django 전환, 운영 적용은 포함하지 않는다.

## 설계
- 2026-09-25 최종 정책: 참조값은 최초 등록에만 사용하고 이후 사용자 입력·재확인을 요구하지 않는다. 관리자가 소속을 정정하며 line은 SDWT에서 도출한다. 최초 등록 시 본인 SDWT의 user 하위 그룹에 가입시키고 이후 소속 속성 변경으로 권한을 자동 변경하지 않는다. Portal 내부 소속·권한 분리 작업은 이번 Keycloak 배포에 포함하지 않는다. 후속 전환은 [SDWT 공통 권한 계획](keycloak-sdwt-group-authorization.md)을 따른다.
- 두 속성은 선택적 단일 문자열이며 관리자만 수정하고 본인은 조회할 수 있다.
- 신규 길이 제한은 임의로 두지 않는다. 실제 참조 테이블 규격이 정해지면 추가한다.
- 별도 소속 claim 목록을 사용해 사내 IdP 수신 mapper와 분리한다.
- ID Token·Access Token·UserInfo에서 같은 이름으로 발급한다.
- 실제 소속과 접근 가능한 조직 목록은 다르며 속성만으로 추가 권한을 부여하지 않는다.
- mock은 필드가 없는 사용자도 로그인 가능한 선택적 출력 mapper를 제공한다.

## 실행 단계
- [x] User Profile과 출력 mapper 추가
- [x] 로컬 mock 및 문서 정합성 반영
- [x] 테스트·export·원본 검사

## 검증
- node --test apps/tooling/tests/environment.test.cjs
- make k8s-export
- make server-check APP=keycloak PROFILE=prod
- make k8s-render-local
- git diff --check

## 위험과 대응
- 사내 로그인 시 소속이 삭제되지 않도록 IdP mapper 목록에 추가하지 않는다.
- 서버 설정만으로 실제 소속값은 생기지 않는다. 관리자 입력 또는 후속 테이블 동기화가 필요하다.

## 진행 기록
- 2026-09-24: 사용자가 두 속성 추가를 승인했다. 기존 사용자·DB를 초기화하지 않는다.
- 2026-09-24: 환경·mapper 테스트 36건 통과. export, Keycloak 서버 원본 검사, 로컬 Kubernetes 렌더, Bash 구문과 diff 검사 통과. 운영 서버 적용·실제 토큰 발급 검증은 수행하지 않았다.
