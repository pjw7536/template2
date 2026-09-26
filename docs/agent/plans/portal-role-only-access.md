# ExecPlan: Portal 역할 기반 앱 접근

## 목표
- 조직별 표준 역할 부여는 Keycloak에서 운영하고 Portal은 client 역할만 판정한다.

## 현재 상태
- deptid와 PORTAL_INTERNAL_DEPT_IDS가 전체 앱 사용을 허용한다.
- portal-all-apps와 개별 앱 역할은 이미 존재한다. 작업 트리에 기존 사용자 변경이 있다.

## 범위
- account/auth 판정·응답, 계정 화면, 배포 client 설정·문서, local realm/env 및 회귀 테스트.
- SDWT 등급, 세션 만료, 기존 사용자 데이터와 운영 서버는 변경하지 않는다.

## 설계
- portal-members 그룹에 portal client의 portal-all-apps를 연결한다. 구성원은 조직 정책에 따라 운영자가 지정한다.
- deptid는 신원 정보만 유지한다. 내부 부서 env와 internal snapshot 판정을 제거한다.
- isInternalMember 대신 hasAllAppsAccess를 응답한다. 이전 snapshot의 internal은 무시한다.
- 로컬 내부 사용자도 동일 그룹으로 역할을 상속한다. DB migration은 없다.

## 실행 단계
- [x] 역할 전용 판정과 회귀 테스트
- [x] Keycloak 표준 그룹·local/env·UI·운영 문서 동기화
- [x] 검증 및 결과 기록

## 검증
- Compose api 컨테이너에서 account/auth/emails의 Keycloak 테스트
- env 도구 테스트, server-check, local render, 수정 shell 구문 검사

## 위험과 대응
- 기존 내부 사용자에게 역할이 없으면 앱 접근이 차단된다. 운영 반영 전 그룹 가입 및 재로그인을 안내한다.
- 기존 Keycloak realm import는 자동 갱신되지 않으므로 로컬 기존 realm의 그룹·역할 반영을 안내한다.

## 진행 기록
- 2026-09-26: 사용자 요청에 따라 기존 전체 앱 권한 의미를 portal-all-apps로 유지한다.

- 2026-09-26: 역할 전용 판정, hasAllAppsAccess 응답·계정 화면, 표준 그룹과 로컬 그룹 상속, env 폐기 및 전환 문서를 반영했다.
- 검증: Compose api 소스 마운트로 account/auth/emails 회귀 47개 통과. environment.test.cjs 42개, server-checkout.test.cjs 17개 통과.
- 검증: server-check portal/prod, local env-profile-key-check, k8s-render-local, 수정 shell bash -n, 계정 화면 ESLint, audit-ui, git diff --check 통과.
- 실제 운영 Keycloak이나 기존 로컬 realm은 변경하지 않았다. 실서버 그룹 역할 상속 로그인은 운영 전환 확인 항목이다.
