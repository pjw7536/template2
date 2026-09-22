# ExecPlan: Keycloak 기본 성·이름 필드 사용

## 목표
- 중복 커스텀 givenname·surname 정의를 제거하고 firstName·lastName을 사용합니다.
- 사용자 본인 조회와 관리자 전용 편집 정책을 유지합니다.

## 현재 상태
- 사내 claim givenname·surname은 커스텀 속성으로 저장됩니다.
- 기본 firstName·lastName은 숨김 상태입니다.

## 범위
- 프로필, 양방향 mapper, 문서, 회귀 검증과 배포 YAML.
- 기존 env 예시 수정은 보존합니다.

## 설계
- givenname → firstName, surname → lastName으로 IdP mapper를 갱신합니다.
- Portal token의 givenname·surname은 기본 property에서 읽고 claim 이름은 유지합니다.
- 활성 15개 프로필 모두 admin/user 조회, admin 편집을 허용합니다.
- 사내 재로그인으로 기본 필드를 채우며 기존 사용자 속성값은 일괄 삭제하지 않습니다.
- 기본 profile scope의 given_name·family_name·name도 기본 필드 값을 사용할 수 있습니다.
- Django·local dummy의 입력 claim과 env·DB 계약은 유지합니다.

## 실행 단계
- [x] 프로필·매퍼·문서 수정
- [x] 기본 필드와 본인 조회 회귀 검증 갱신
- [x] 배포 YAML 재생성 및 검증

## 검증
- make k8s-export
- bash -n deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh
- node --test apps/tooling/tests/environment.test.cjs
- git diff --check

## 위험과 대응
- IdP·Portal Job을 연속 실행하고 사내 재로그인 후 값을 확인합니다.
- 이전 first_name·last_name mapper는 계속 제거하여 새 기본 이름 값을 덮어쓰지 않게 합니다.

## 진행 기록
- 2026-09-15: 사용자 요청대로 기본 필드 사용으로 방향 변경. 본인 조회 정책 유지.
- 2026-09-15: YAML 생성, Bash 구문, 환경 회귀 35개, diff 공백 검사 통과. local dummy와 Django는 기존 claim 이름을 사용하므로 추가 변경 불필요. 실서버 적용 및 재로그인 검증은 미실행입니다.
