# ExecPlan: 승인 대기 요청 무한 스크롤

## 목표
- 승인 대기 요청 목록의 페이지 이동 버튼을 제거한다.
- 목록 하단에 가까워지면 다음 서버 페이지를 자동으로 불러온다.
- 로딩, 마지막 페이지, 다음 페이지 오류 상태를 명확하게 표시한다.
- 권한 관리 화면에서 바깥 페이지와 탭 콘텐츠의 중복 세로 스크롤을 제거한다.

## 현재 상태
- `usePendingAccessRequests`는 페이지 번호를 받는 일반 React Query 쿼리다.
- `PermissionsPage`가 승인 대기 페이지 상태를 직접 관리한다.
- `PendingAccessPanel`은 공용 `AccountDataTable`의 페이지네이션 푸터를 사용한다.
- 서버 응답은 `pagination.page`와 `pagination.totalPages`를 제공한다.

## 범위
- 승인 대기 요청 쿼리를 `useInfiniteQuery`로 변경한다.
- 불러온 서버 페이지의 요청을 하나의 목록으로 합친다.
- 공용 테이블에 스크롤 하단 상태 영역과 내용이 짧을 때의 자동 로드를 지원한다.
- 권한 관리 페이지는 높이만 배분하고, 활성 탭의 데이터 영역 하나만 세로 스크롤을 소유하게 한다.
- API, DB, 인증·권한 규칙은 변경하지 않는다.

## 설계
- 쿼리 키에 `infinite`, 페이지 크기, 권한 범위를 포함한다.
- `getNextPageParam`은 마지막 응답의 현재 페이지와 전체 페이지를 비교한다.
- 선택 체크박스는 현재까지 불러온 요청 전체를 대상으로 한다.
- 다음 페이지 오류는 기존 목록을 유지하고 하단 재시도 버튼으로 복구한다.
- public facade, migration, env, auth contract 영향은 없다.

## 실행 단계
- [x] 승인 대기 요청 쿼리를 무한 쿼리로 전환한다.
- [x] 페이지 상태와 페이지 변경 prop을 제거한다.
- [x] 스크롤 하단 자동 로드와 상태·재시도 UI를 연결한다.
- [x] 린트, 빌드, 프론트엔드 경계·UI 일관성 점검을 실행한다.
- [x] 권한 관리 페이지와 각 탭 패널의 높이·overflow 소유권을 통일한다.
- [x] 중복 스크롤 제거 후 린트, 빌드, 레이아웃 감사를 다시 실행한다.

## 검증
- 변경 파일 ESLint
- 웹 프로덕션 빌드
- `scripts/agent/check_frontend_boundaries.sh`
- `scripts/agent/check_ui_consistency.sh`
- `git diff --check`

## 위험과 대응
- 위험: 다음 페이지 로드 중 기존 목록이 오류 화면으로 대체될 수 있다.
- 대응: 최초 로드 오류와 다음 페이지 오류를 분리한다.
- 위험: 첫 페이지가 스크롤 영역보다 짧으면 스크롤 이벤트가 발생하지 않는다.
- 대응: 행 수가 바뀔 때 스크롤 높이를 점검해 다음 페이지를 자동 요청한다.
- 위험: 좁은 화면에서 바깥 스크롤을 제거하면 탭 콘텐츠가 잘릴 수 있다.
- 대응: 페이지부터 탭 패널까지 `h-full`과 `min-h-0`를 연속 적용하고 실제 데이터 영역에만 `overflow-auto`를 둔다.
- 위험: shadcn Table의 가로 스크롤 래퍼가 CSS 계산상 세로 스크롤도 소유할 수 있다.
- 대응: 승인 대기 탭에서는 내부 Table 래퍼의 overflow를 해제하고 `AccountDataTable` 스크롤 영역이 양축을 단독 소유한다.

## 진행 기록
- 2026-07-29: 기존 API 계약을 유지하는 프론트엔드 무한 스크롤 설계를 확정했다.
- 2026-07-29: 서버 페이지 병합, 하단 자동 로드, 추가 로드 오류 재시도, 불러온 요청 전체 선택을 구현했다.
- 2026-07-29: 변경 파일 ESLint, 웹 빌드, frontend boundary audit, `git diff --check`를 통과했다.
- 2026-07-29: UI consistency audit는 기존 `l3-spider` raw color/inline style과 동적 열 너비용 `AccessPolicyPanel` CSS 변수 사용을 검토 대상으로 보고했다.
- 2026-07-29: 후속 요청에 따라 권한 관리 화면의 세로 스크롤 소유자를 활성 탭의 데이터 영역 하나로 통일하기로 했다.
- 2026-07-29: 페이지와 탭 컨테이너의 overflow를 숨기고 각 탭의 데이터 영역만 `overflow-auto`를 소유하도록 변경했다.
- 2026-07-29: 변경 파일 ESLint, 웹 빌드, frontend boundary audit, `git diff --check`를 다시 통과했다. UI consistency audit의 기존 검토 후보는 동일하다.
- 2026-07-29: 승인 대기 테이블 내부의 `table-container`가 `overflow-x-auto`로 인해 중첩 세로 스크롤을 생성하는 원인을 확인하고, 해당 탭에서 내부 overflow를 해제했다.
