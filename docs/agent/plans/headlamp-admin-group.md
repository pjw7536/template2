# ExecPlan: Headlamp 관리자 그룹 전환

## 목표
- 조회 전용 그룹을 headlamp-admins 그룹으로 교체하고 cluster-admin을 부여한다.

## 현재 상태
- Helm values에 viewer 및 discovery RBAC가 있다.
- Keycloak 그룹은 운영자가 관리하며 OIDC groups claim과 headlamp: prefix를 사용한다.

## 범위
- deploy/headlamp의 RBAC, 운영 안내, apps/tooling의 Headlamp 렌더 회귀 테스트와 결정 기록.
- 로컬 개발 환경과 다른 앱은 변경하지 않는다.

## 설계
- 새 server-headlamp-admin 바인딩으로 roleRef 불변 필드 변경을 피한다.
- 이전 viewer/discovery 리소스는 Helm upgrade 시 제거한다.
- Keycloak 관리자 그룹은 별도로 만들고 필요한 관리자만 가입시킨 후 이전 그룹을 제거한다.

## 실행 단계
- [x] RBAC와 운영 문서 변경
- [x] 회귀 테스트 및 서버 설정 검사

## 검증
- python3 -m unittest discover -s deploy/headlamp/tests
- make server-check APP=headlamp PROFILE=prod
- make headlamp-check
- git diff --check

## 위험과 대응
- 전체 관리 권한은 사용자가 명시 승인했다. 그룹 외 사용자와 기존 viewer 권한 차단을 검사한다.
- 실제 서버 설정과 그룹 가입은 운영 환경에서 별도 적용·검증한다.

## 진행 기록
- 2026-09-24: 사용자가 모든 관리 권한 부여를 확정했다.
- 2026-09-24: 임시 Helm 3.17.3을 공식 배포본 SHA-256 확인 후 사용했다. Python 입력 검증을 포함한 Node 테스트 2건, server-check, headlamp-check 통과. 운영 context가 없어 실제 배포·Keycloak 그룹 생성은 수행하지 않았다.
