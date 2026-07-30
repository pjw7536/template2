# ExecPlan: 사용자 전체 권한 일괄 변경

## 목표
- 권한 매트릭스의 Portal 원형 메뉴에서 선택한 권한 값을 해당 사용자의 모든 활성 권한에 한 번에 적용한다.

## 현재 상태
- 개별 원형 셀에서 scope 하나의 권한만 변경할 수 있다.
- Portal 원형 메뉴의 일괄 적용 옵션은 일반 권한만 적용해 관리자, 접근 차단, 자동 규칙 선택을 반영하지 못한다.
- 단일 권한 변경 API는 최신 `matrixRow`를 반환하며 frontend는 해당 사용자 행만 캐시에서 교체할 수 있다.

## 범위
- Portal을 포함해 권한 매트릭스에 표시되는 모든 활성 scope를 일괄 변경한다.
- 선택값 `inherit`, `user`, `admin`, `denied`를 모든 대상 scope에 동일하게 적용한다.
- `inherit`는 명시 권한을 제거하고, `user`와 `admin`은 해당 역할로 허용하며, `denied`는 명시적으로 차단한다.
- 슈퍼유저 불변 규칙과 Portal admin 관리 권한 검사는 유지한다.
- 각 실제 변경 scope에 감사 로그를 남긴다.
- 정책 규칙, DB schema, 기존 개별 권한 변경 계약은 변경하지 않는다.

## 설계
- `POST /api/v1/account/access/users/<user_id>/apply-all` 엔드포인트는 `{ "value": "inherit|user|admin|denied" }` 입력을 받는다.
- backend 서비스는 단일 transaction 안에서 대상 사용자를 잠그고, 매트릭스의 모든 활성 scope를 순회해 선택값을 적용한다.
- 이미 선택값과 동일한 scope는 쓰기와 감사 로그를 생략한다.
- 응답에 변경 요약과 최신 `matrixRow`를 포함한다.
- frontend는 Portal 원형 메뉴에서 선택값과 일괄 적용 체크 상태를 함께 전송하고, 성공 응답의 `matrixRow`로 해당 행만 갱신한다.

## 실행 단계
- [x] backend 일괄 변경 서비스와 API endpoint를 선택값 기반으로 일반화한다.
- [x] 전체 활성 scope 변경, 비활성 제외, 감사 로그, 슈퍼유저 거절 테스트를 보강한다.
- [x] frontend API와 React Query mutation을 선택값 기반으로 변경한다.
- [x] Portal 원형 메뉴의 선택값과 일괄 적용 체크박스를 공통 `권한 변경` 버튼에 연결한다.
- [x] backend 테스트, frontend lint/build, 경계/UI 감사를 실행한다.

## 검증
- Docker Compose `api` 컨테이너에서 선택값 네 종류와 기존 매트릭스 회귀 테스트 14건 통과.
- 변경한 frontend 파일 ESLint 통과.
- frontend production build 통과. 기존 large chunk 경고만 발생.
- backend/frontend boundary audit 통과.
- UI consistency audit는 이번 변경과 무관한 기존 `l3-spider` raw color/inline style 후보만 보고했다.
- `git diff --check` 통과.
- `makemigrations --check --dry-run` 결과 변경 없음.

## 위험과 대응
- 위험: 일부 scope만 저장된 뒤 실패하면 권한 상태가 부분 반영될 수 있다.
- 대응: 전체 변경을 하나의 `transaction.atomic()`으로 처리한다.
- 위험: 선택값과 저장 상태 매핑이 달라 일부 scope에 다른 권한이 남을 수 있다.
- 대응: 네 가지 선택값별 저장 상태를 명시하고 전체 활성 scope 결과를 테스트한다.
- 위험: 대규모 사용자 목록을 다시 조회해 기존 성능 문제가 재발할 수 있다.
- 대응: 서버가 반환한 최신 `matrixRow`만 React Query infinite cache에서 교체한다.

## 진행 기록
- 2026-07-29: 사용자 이름 클릭 후 모든 활성 매트릭스 권한을 일반 사용자로 부여하는 계약을 확정했다.
- 2026-07-29: transaction 기반 일괄 부여 endpoint와 최신 `matrixRow` 응답을 추가했다.
- 2026-07-29: 사용자 이름 클릭 확인 Dialog와 단일 행 캐시 교체 mutation을 연결했다.
- 2026-07-29: backend 테스트 7건, frontend ESLint/build, 양쪽 boundary audit와 migration 검사를 완료했다.
- 2026-07-29: 사용자 피드백에 따라 진입점을 이름 클릭에서 Portal 원형 메뉴의 “모든 앱·기능 권한 함께 승인”으로 변경하고 frontend 검증을 다시 완료했다.
- 2026-07-29: 원형 메뉴의 상태 정보를 `접근 가능/불가`, 실제 권한, 자연어 설명으로 단순화하고 개별 변경과 일괄 승인을 별도 구역으로 재배치했다.
- 2026-07-29: 별도 일괄 승인 항목과 확인 Dialog를 제거하고, Portal 메뉴의 일괄 적용 체크박스와 공통 실행 버튼으로 통합했다.
- 2026-07-29: 사용자 피드백에 따라 일괄 적용의 의미를 일반 권한 승인에서 현재 선택값의 전체 앱·기능 적용으로 변경했다.
- 2026-07-29: 체크박스를 Portal 메뉴의 `권한 변경` 문구 오른쪽으로 옮기고, 네 가지 선택값의 전체 적용 및 회귀 검증을 완료했다.
