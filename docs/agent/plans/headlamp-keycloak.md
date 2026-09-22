# ExecPlan: Headlamp Keycloak 로그인

## 목표
- 서버 Headlamp에서 Keycloak으로 로그인하고 headlamp-viewers 그룹만 기존 조회 권한을 사용한다.

## 현재 상태
- deploy/headlamp는 v0.45.0 chart와 1시간 ServiceAccount 토큰을 사용한다.
- Keycloak etch realm이 있으며 Kubernetes OIDC 설정은 저장소에 없다.
- 현재 실행 환경에는 kind-tailwind-local context만 있어 사내 배포·실제 로그인 검증은 불가하다.
- 작업 시작 전부터 여러 사용자 변경이 있으며 해당 변경을 보존한다.

## 범위
- deploy/headlamp 설정·검사·Keycloak client 생성·운영 문서와 관련 테스트.
- 로컬 토큰 접속 구성은 유지한다. 운영 제어면을 추측해서 수정하지 않는다.

## 설계
- Headlamp → Keycloak authorization code → ID token → Kubernetes OIDC 인증 → 그룹 RBAC.
- username은 sub, prefix는 headlamp:; groups는 groups, prefix는 headlamp:.
- Keycloak 그룹 full path /headlamp-viewers를 headlamp:/headlamp-viewers에 바인딩한다.
- client secret은 기존 Kubernetes Secret 참조로 주입하고 Helm 값·출력에 포함하지 않는다.
- issuer·client ID·Secret·선택 CA ConfigMap은 env 입력. HTTPS 공개 callback을 고정한다.
- 기존 viewer ServiceAccount를 제거하며 비상 복구는 관리자 kubeconfig로 수행한다.

## 실행 단계
- [x] OIDC 입력·Secret/CA 사전 검사와 client import JSON 생성 구현
- [x] 그룹 RBAC와 운영 문서 전환
- [x] 단위 테스트·실제 고정 chart 렌더·서버 경계 검사

## 검증
- python3 -m unittest discover -s deploy/headlamp/tests -v
- node --test apps/tooling/tests/headlamp-deployment.test.cjs
- make server-check APP=headlamp PROFILE=prod
- 공식 chart는 lock SHA-256 검증 후 /tmp에서 사용한다. Helm도 /tmp 도구를 사용한다.
- 사내 API server OIDC·DNS·CA·실제 로그인과 그룹 외 사용자 거부는 서버 인수 절차로 남긴다.

## 위험과 대응
- 제어면 OIDC 미설정 시 로그인 후 401: 배포 전 인프라 설정 및 사용자 토큰 인수 검사.
- 다른 RBAC가 권한을 추가할 수 있음: 전용 prefix, 기존 바인딩·view 집계 권한 검사.
- Secret·CA 누락: 배포 전 검사. 인증서 검증을 끄지 않는다.

## 진행 기록
- 2026-09-22: 사용자 그룹 제한 선택 확정. 공식 OIDC 문서와 고정 chart 계약 확인.

- 2026-09-22: 구현·문서 완료. Python 단위 검사 11개, 실제 chart 렌더 통합 검사 2개, 서버 checkout 검사 17개 통과. `make server-check APP=headlamp PROFILE=prod` 및 `git diff --check` 통과.
- 2026-09-22: 운영 환경 설정·Keycloak 등록·제어면 변경·실제 로그인은 미수행. 사내 context가 없으므로 OIDC.md의 서버 인수 절차가 남아 있다.
