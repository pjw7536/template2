# ExecPlan: 자동 접근 규칙 매트릭스

## 목표
- 자동 접근 규칙을 부서별 Portal·전체 활성 앱·기능 매트릭스로 표시하고 개별 또는 전체 상태를 한 번에 변경한다.

## 현재 상태
- frontend는 하나의 scope를 선택한 뒤 해당 scope의 부서 규칙 목록만 표시한다.
- backend는 scope 하나의 규칙 CRUD만 제공하며, 정책 규칙 모델은 scope·부서 조합별 활성 상태를 저장한다.
- 규칙이 없는 scope는 자동 접근을 허용하지 않는다.

## 범위
- 매트릭스 행은 등록된 부서, 열은 Portal과 모든 활성 앱·기능으로 구성한다.
- 셀은 `사용 중 / 사용 안 함` 두 상태만 표시한다.
- 규칙이 없는 셀은 `사용 안 함`으로 표시하고 활성화 시 규칙을 생성한다.
- 행 단위 전체 적용은 Portal과 모든 열을 같은 상태로 변경한다.
- 기존 단일 규칙 CRUD API와 DB schema는 유지한다.

## 설계
- 정책 목록 API의 `scope=all` 조회를 추가해 모든 scope 규칙을 반환한다.
- `POST /api/v1/account/access/policy-rules/bulk-apply`는 부서, scope key 목록, 활성 상태를 받아 한 transaction에서 규칙을 생성하거나 갱신한다.
- 실제 변경 규칙마다 기존 정책 생성·수정 감사 로그를 남기고 동일 상태는 쓰기를 생략한다.
- frontend는 기존 규칙 목록을 부서×scope 행으로 변환하고 셀 토글은 scope 하나, 전체 토글은 모든 표시 scope key를 전송한다.
- 새 부서 추가는 모든 표시 scope에 같은 초기 상태를 적용한다.
- 모델·migration·인증 규칙은 변경하지 않는다.

## 실행 단계
- [x] 전체 scope 정책 조회와 일괄 적용 serializer/service/view/route를 추가한다.
- [x] 생성·갱신·무변경·scope 검증·transaction 감사 로그 테스트를 추가한다.
- [x] 기존 정책 목록 UI를 고정 헤더와 가로 스크롤을 가진 매트릭스로 교체한다.
- [x] 새 부서, 개별 셀, 행 전체 상태 변경을 일괄 적용 mutation에 연결한다.
- [x] backend 테스트, migration 검사, frontend lint/build, 경계/UI 감사를 실행한다.

## 검증
- Docker Compose `api` 컨테이너에서 정책 API 관련 회귀 테스트 7건 통과.
- `makemigrations --check --dry-run` 결과 schema 변경 없음.
- 변경 frontend 파일 ESLint와 production build 통과. 기존 large chunk 경고만 발생.
- backend/frontend boundary audit 통과.
- UI consistency audit는 이번 변경과 무관한 기존 `l3-spider` raw color/inline style 후보만 보고했다.
- `git diff --check` 통과.

## 위험과 대응
- 위험: 전체 적용 중 일부 scope만 변경될 수 있다.
- 대응: scope를 안정된 순서로 잠그고 모든 upsert와 감사 로그를 하나의 transaction에서 처리한다.
- 위험: 기존에 규칙이 없는 셀과 비활성 규칙이 화면에서 다르게 보일 수 있다.
- 대응: 두 상태 UI 계약에 따라 둘 다 `사용 안 함`으로 표시하며, 활성화 시 동일하게 upsert한다.
- 위험: scope별 반복 요청으로 화면과 서버 상태가 어긋날 수 있다.
- 대응: 전체 적용 전용 endpoint 한 번으로 처리하고 성공 후 정책·매트릭스 관련 query만 무효화한다.

## 진행 기록
- 2026-07-29: 사용자가 Portal 포함과 `사용 중 / 사용 안 함` 두 상태 매트릭스를 확정했다.
- 2026-07-29: 전체 scope 조회, transaction 기반 일괄 upsert API, 부서×scope 매트릭스 UI와 검증을 완료했다.
