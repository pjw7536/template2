# ExecPlan: Keycloak 사내 claim 저장 이름 통일

## 목표
- 커스텀 속성 loginid, deptname, grdName을 사내 수신·저장·발급에서 동일하게 사용한다.

## 현재 상태
- 기존 저장 이름은 knox_id, department, grd_name이며 토큰 이름은 이미 사내 계약이다.
- 기본 필드 username은 EPID, 사람 이름은 display_name으로 구분한다.

## 범위
- Keycloak 프로필, mapper, CSV 초기 등록, 이전 값 복사 도구, 관련 문서·검증·렌더.
- Portal DB와 외부 토큰 계약은 유지한다.

## 설계
- 기본 필드 충돌 예외를 유지하고 커스텀 속성 세 개만 변경한다.
- 기존 사용자는 dry-run 기본 도구로 누락된 새 속성에 이전 값을 복사한다. 충돌은 쓰기 전에 차단하고 이전 값은 보존한다.
- 초기 등록의 계정 충돌 검사는 이전 loginid 별칭도 확인한다.

## 실행 단계
- [x] 프로필·mapper·초기 등록을 변경한다.
- [x] 기존 값 복사 도구와 회귀 검증을 추가한다.
- [x] 문서·렌더를 최신화하고 검증한다.

## 검증
- Node environment/server-checkout 검사, Python Keycloak 검사, make server-check APP=keycloak PROFILE=prod.

## 위험과 대응
- 기존 세션 토큰 재발급 시 빈 claim: 2번 프로필 → 이전 값 복사 → 3번 IdP → 4번 client 순서로 전환한다.
- 동시 사용자 수정: 작업 시간 동안 로그인·관리자 편집을 멈추고 각 저장 직전에 속성을 재확인한다.
- 서버 쓰기는 운영자가 명시적으로 실행하며 이번 작업에서는 수행하지 않는다.

## 진행 기록
- 2026-09-25: 구현 범위와 기존 값 보존 전환을 확정했다.

- 검증 완료: Node environment/server-checkout 58개 통과, Python Keycloak 28개 통과·실서버 테스트 9개 건너뜀. make server-check와 k8s-export 통과.
- 로컬 Keycloak 원본에는 해당 이전 커스텀 속성 정의가 없어 수정하지 않았다. 실제 서버 적용·값 복사·로그인 검증은 수행하지 않았다.
