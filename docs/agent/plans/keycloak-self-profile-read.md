# ExecPlan: Keycloak 본인 프로필 조회 허용

## 목표
- 사용자가 본인의 활성 프로필 정보를 모두 읽을 수 있도록 합니다.

## 현재 상태
- username만 user 조회 권한이 있고 나머지는 관리자만 조회할 수 있습니다.
- firstName·lastName은 이전 요청에 따라 숨긴 기본 필드입니다.

## 범위
- 프로필 권한, 관련 안내, 회귀 검증, 배포 YAML을 변경합니다.
- 기존 env 예시 사용자 변경은 보존합니다.

## 설계
- 활성 15개 필드의 view를 admin/user, edit를 admin으로 유지합니다.
- 숨긴 두 기본 필드와 미정의 과거 속성의 ADMIN_EDIT 정책을 유지합니다.
- 토큰·IdP 계약과 DB·env 변경은 없습니다. local mock 변경도 필요 없습니다.

## 실행 단계
- [x] 프로필 조회 권한과 문서 변경
- [x] 본인 조회 및 관리자 전용 편집 회귀 검증 갱신
- [x] 배포 YAML 생성 및 검증

## 검증
- make k8s-export
- node --test apps/tooling/tests/environment.test.cjs
- git diff --check

## 위험과 대응
- 조회 권한만 추가하고 user 편집 권한은 주지 않습니다.
- 실서버 반영은 최신 claim Job 실행이 필요합니다.

## 진행 기록
- 2026-09-15: 필드 구성을 유지하는 본인 조회 변경으로 범위를 확정했습니다.
- 2026-09-15: 배포 YAML 생성, 환경 회귀 테스트 35개, diff 공백 검사 통과. 실서버 적용·계정 화면 검증은 미실행입니다.
- 2026-09-15: 후속 요청으로 firstName·lastName을 활성화하고 중복 커스텀 속성을 제거합니다. 최신 설계는 keycloak-standard-name-fields.md를 따릅니다.
