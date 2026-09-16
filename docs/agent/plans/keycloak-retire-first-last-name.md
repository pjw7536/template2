# ExecPlan: Keycloak 성·이름 중복 필드 정리

## 목표
- first_name·last_name 매핑을 폐기하고 givenname·surname을 유지합니다.

## 현재 상태
- 사내 응답에는 first_name·last_name이 없고 한글 이름은 username으로 전달됩니다.
- Keycloak 기본 firstName·lastName 정의는 삭제할 수 없습니다.

## 범위
- Keycloak 프로필 권한, IdP·Portal mapper 스크립트, 배포 산출물, 안내와 회귀 검증.
- EPID와 Django 사용자 모델·이름 보완 로직은 변경하지 않습니다.

## 설계
- 기본 firstName·lastName은 view/edit 권한을 비워 숨깁니다.
- 두 legacy claim을 동기화 목록에서 제거하고 기존 mapper도 대상별로 삭제합니다.
- givenname·surname과 username → display_name은 유지합니다.
- 사용자 데이터 일괄 변경과 DB migration, env 변경은 없습니다.
- local dummy는 이미 두 legacy claim을 보내지 않으므로 변경이 필요 없습니다.

## 실행 단계
- [x] 프로필과 mapper, 문서 수정
- [x] 기존 mapper 삭제와 유지 필드 회귀 검증 갱신
- [x] YAML 재생성 및 검증 실행

## 검증
- bash -n deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh
- bash deploy/keycloak/scripts/render.sh
- node --test apps/tooling/tests/environment.test.cjs
- git diff --check

## 위험과 대응
- 기본 필드 삭제는 Keycloak 제약과 충돌하므로 정의를 유지하고 권한을 비웁니다.
- 기존 매퍼가 남지 않도록 idp/client 대상별 삭제를 검증합니다.
- 공유 profile client scope의 표준 claim과 과거 사용자 값은 별도 계약이므로 일괄 삭제하지 않습니다.

## 진행 기록
- 2026-09-15: 요청 범위와 Keycloak 기본 필드 제약을 확인했습니다. 실서버 적용은 하지 않습니다.
- 2026-09-15: YAML 재생성, Bash 구문 검사, 환경 회귀 테스트 35개, diff 공백 검사 통과. local dummy·Compose·env·Django 호출부 확인 결과 추가 wiring 변경은 필요 없습니다. 실서버 UI/API 검증은 미실행입니다.
