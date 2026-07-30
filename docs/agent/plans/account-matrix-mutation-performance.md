# ExecPlan: 대규모 권한 매트릭스 단일 변경 성능 개선

## 목표
- 많은 페이지를 불러온 권한 매트릭스에서도 특정 사용자 한 명의 권한 변경이 목록 크기에 비례해 느려지지 않게 한다.

## 현재 상태
- 단일 권한 변경 성공 시 `ACCESS_MATRIX_QUERY_KEY` 전체를 invalidate한다.
- React Query infinite query가 이미 불러온 모든 페이지를 다시 조회하므로 목록이 클수록 mutation 완료가 늦어진다.
- mutation 상태와 대상 셀 key가 전체 매트릭스에 전달되어 모든 셀이 다시 렌더링된다.
- 권한 변경 API 응답은 변경한 scope 하나의 접근 결과만 반환해 Portal 연쇄 판정을 로컬에서 정확히 갱신하기 어렵다.

## 범위
- 단일 사용자 권한 변경 API 응답에 해당 사용자의 최신 전체 매트릭스 행을 추가한다.
- 일반 매트릭스 캐시는 전체 invalidate 대신 해당 사용자 행만 교체한다.
- 수동 부여 필터 캐시는 포함 여부가 변할 수 있으므로 백그라운드 재조회한다.
- 셀 컴포넌트를 memoize하고 대상 셀만 pending 상태가 바뀌도록 한다.
- bulk approval, DB schema, auth/permission 규칙은 변경하지 않는다.

## 설계
- backend는 기존 매트릭스 판정 로직을 공용 단일 행 serializer로 추출한다.
- 단일 결정 API만 `matrixRow`를 추가하고, bulk approval 내부 호출은 추가 조회를 수행하지 않는다.
- frontend mutation 성공 시 infinite query의 `pages[].results[]`에서 같은 user ID 행만 구조 공유를 유지하며 교체한다.
- 관련 목록과 인증 정보는 mutation 완료를 막지 않는 백그라운드 invalidation으로 갱신한다.
- `manualGrantOnly=true` query는 membership 변경 가능성 때문에 백그라운드 invalidate한다.

## 실행 단계
- [x] 매트릭스 단일 행 serializer를 추출하고 결정 응답에 `matrixRow`를 추가한다.
- [x] Portal 변경의 하위 scope 연쇄 결과까지 포함하는 backend 테스트를 추가한다.
- [x] React Query infinite cache의 단일 행 교체 helper를 구현한다.
- [x] 셀 pending prop과 callback을 안정화하고 `React.memo`를 적용한다.
- [x] backend 테스트, frontend lint, boundary/UI audit를 실행한다.

## 검증
- Docker Compose `api` 컨테이너에서 관련 account 테스트 6건 통과.
- 변경한 frontend 파일 ESLint 통과.
- frontend production build 통과. 기존 large chunk 경고만 발생.
- `python3 scripts/agent/check_backend_boundaries.py` 통과.
- `scripts/agent/check_ui_consistency.sh`는 이번 변경과 무관한 기존 `l3-spider` raw color/inline style 후보 때문에 실패했으며, 변경 파일에서는 후보가 발견되지 않았다.
- `git diff --check` 통과.
- DB schema 변경이 없어 migration은 생성하지 않았다.

## 위험과 대응
- 위험: Portal 변경 시 하위 scope의 최종 접근 결과가 오래된 상태로 남을 수 있다.
- 대응: 변경된 scope 하나가 아니라 서버가 계산한 전체 사용자 행으로 교체한다.
- 위험: 수동 부여 필터에서 사용자가 포함/제외되어야 할 수 있다.
- 대응: 해당 필터 query만 백그라운드 재조회한다.
- 위험: bulk approval이 사용자 수만큼 전체 행을 추가 조회할 수 있다.
- 대응: `matrixRow` 생성은 단일 결정 API에만 적용하고 bulk 내부 서비스는 기존 응답 비용을 유지한다.

## 진행 기록
- 2026-07-29: 전체 infinite query invalidation과 전 셀 mutation prop 전파를 주요 병목으로 확인했다.
- 2026-07-29: 단일 결정 응답에 서버 판정 전체 행을 추가하고, 일반 infinite cache에서 해당 사용자 행만 교체하도록 변경했다.
- 2026-07-29: 수동 부여 필터 및 보조 query만 백그라운드 갱신하도록 분리하고, 셀 memoization과 안정적인 callback을 적용했다.
- 2026-07-29: backend 관련 테스트 6건, frontend ESLint/build, backend boundary audit, diff 검사를 완료했다.
