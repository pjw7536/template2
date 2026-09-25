# ExecPlan: 현재 Keycloak과 Headlamp 로그인 연결

## 목표
- 현재 Keycloak 자체 설정을 완료한 운영자가 Headlamp 전용 client부터 배포·권한 확인까지 진행할 수 있다.
- TLS·issuer·서명키 오류를 배포 전에 확인한다.

## 현재 상태
- Headlamp 0.45.0, 전용 client JSON, Secret·CA 참조와 관리자 그룹 RBAC가 이미 있다.
- Keycloak은 etch realm, oidc IdP, EPID 기본 username과 loginid를 사용한다.
- Keycloak 관련 미커밋 변경은 사용자 작업으로 보존한다.

## 범위
- deploy/headlamp의 관리 도구·테스트·문서, 루트 Make 진입점.
- Keycloak·Portal 설정이나 실제 클러스터 권한은 변경하지 않는다.

## 설계
- 기존 ID Token 인증을 명시하고 전용 그룹·sub 기반 권한 계약을 유지한다.
- 별도 oidc-check 명령으로 HTTPS discovery의 issuer·code flow·RS256·JWKS를 검증한다.
- CA는 명시한 로컬 파일로 읽고 TLS 검증을 유지한다. 정적 검사에는 네트워크를 요구하지 않는다.
- README를 설치 순서 안내로 정리하고 환경변수·실행 안내를 연결한다.

## 실행 단계
- [x] 현재 Keycloak·Headlamp 설정 및 upstream 고정 버전 확인
- [x] OIDC 사전 검사·Make 진입점·회귀 테스트 구현
- [x] 설치·환경·사내 계정 연결 설명 정리
- [x] 관련 검사 실행 및 결과 기록

## 검증
- python3 -m unittest discover -s deploy/headlamp/tests -v
- node --test apps/tooling/tests/headlamp-deployment.test.cjs apps/tooling/tests/server-checkout.test.cjs
- make server-check APP=headlamp PROFILE=prod 및 make headlamp-check
- git diff --check

## 위험과 대응
- 실제 서버·사내 CA·대상 context가 제공되지 않았다. 실제 로그인 성공과 오프라인 검증을 구분한다.
- Headlamp 서버의 discovery 성공은 Pod·API server의 네트워크 접근이나 사용자 RBAC 성공을 보장하지 않는다.
- 기존 사용자 Keycloak 변경은 읽기만 하고 Headlamp에 계약을 반영한다.

## 진행 기록
- 2026-09-25: 기존 인증·권한 계약을 유지하며 연결 사전 검사와 단계별 안내를 보강하기로 결정.
- 2026-09-25: Python 14개, Node 배포·서버 checkout 19개 테스트 통과. server-check와 headlamp-check, client JSON 생성, git diff --check 통과.
- 검증 환경의 PATH에 Helm이 없어 기존 `/tmp/tailwind-commit-tools/linux-amd64/helm`을 `HELM_BIN`으로 지정했다.
- 실제 대상 context·사내 CA가 제공되지 않아 운영 OIDC 연결 검사, 클러스터 배포·브라우저 로그인은 실행하지 않았다. 문서의 완료 기준으로 남겼다.
