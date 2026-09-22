# ExecPlan: 삭제한 직급 매핑 복원

## 목표
- 사내 grdName → Keycloak grd_name → Portal grdName 매핑을 복원합니다.

## 현재 상태
- grdName은 매퍼 삭제 대상이며 프로필에는 grdname_en만 있습니다.
- Django와 local dummy는 기존 grdName 계약을 유지하고 있습니다.

## 범위
- 프로필, 매퍼, 배포 YAML, 문서, 회귀 검증.
- 이름 필드·본인 조회 변경과 기존 사용자 env 변경은 보존합니다.

## 설계
- grd_name은 길이 150, 본인·관리자 조회, 관리자 편집 정책을 사용합니다.
- grdName을 동기화 목록으로 복원하고 삭제 대상에서 제외합니다.
- DB·env·local dummy 변경은 필요 없습니다.

## 실행 단계
- [x] 직급 프로필·매핑과 문서 복원
- [x] 삭제 방지·기존 매퍼 갱신 회귀 검증
- [x] 배포 YAML 생성 및 검증

## 검증
- make k8s-export
- bash -n deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh
- node --test apps/tooling/tests/environment.test.cjs
- git diff --check

## 위험과 대응
- 실제 값 반영은 두 매퍼 Job 적용 후 사내 재로그인으로 확인합니다.

## 진행 기록
- 2026-09-15: 새 소문자 claim 대신 삭제 전 grdName 계약으로 복원합니다.
- 2026-09-15: YAML 생성, Bash 구문 검사, 회귀 테스트 35개, diff 공백 검사 통과. 실서버 적용은 미실행입니다.
- 2026-09-15: main 반영 전 tooling 전체 60개 및 Keycloak 배포 회귀 테스트 통과. Portal Job 렌더링과 두 배포 YAML의 원본 일치 확인. 비밀번호가 입력된 사용자 수정 env 예시는 커밋에서 제외하고 로컬에 보존합니다.
