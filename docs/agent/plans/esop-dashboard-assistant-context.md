# ExecPlan: ESOP Dashboard Assistant 배경지식 전달 복구

## 목표
- ESOP Dashboard ChatWidget이 현재 화면의 라인/기간/라인 필터/최근 시간 범위와 동일한 서버 snapshot을 배경지식으로 전달한다.
- 화면에는 데이터가 있지만 Assistant 조회가 0건으로 끝나는 불일치를 제거한다.

## 현재 상태
- ESOP status 표는 `lineFilterMode`에 따라 대상 분임조 매핑 또는 직접 `line_id`로 조회한다.
- Assistant snapshot은 직접 `line_id`만 조회하여 매핑으로 노출된 행을 누락한다.
- status 화면의 실제 날짜와 최근 시간 필터가 Assistant page context에 포함되지 않는다.
- Observer 배경지식 source count 보정 변경은 별도 미커밋 상태로 보존되어 있다.

## 범위
- line-dashboard page context에 실제 화면 필터를 포함한다.
- assistant Tool 입력 정규화와 runtime 전달을 확장한다.
- drone snapshot selector가 표 조회와 같은 라인 필터 및 최근 시간 범위를 적용하도록 한다.
- 관련 frontend/backend 회귀 테스트를 추가한다.
- DB schema, migration, auth, env, 외부 API는 변경하지 않는다.

## 설계
- status 화면의 query state를 소유한 `useDataTableState`에서 Assistant context를 등록한다.
- status Tool 입력은 `lineFilterMode`, `recentHoursStart`, `recentHoursEnd`를 필수 필드로 전달하고 history 입력과 명확히 분리한다.
- backend는 현재 화면 종류별 정확한 필드 집합과 값 범위를 검증한 뒤 selector에 전달하며 과거 입력 fallback은 두지 않는다.
- selector는 기존 표 API와 동일하게 직접 `line_id` 또는 대상 매핑을 OR 조건으로 적용한다.
- public facade, DB migration, env/auth 계약 영향은 없다.

## 실행 단계
- [x] frontend의 실제 status 필터를 Assistant page context에 연결한다.
- [x] assistant Tool 입력과 runtime 전달을 확장한다.
- [x] drone snapshot 조회 범위를 표 API와 일치시킨다.
- [x] frontend/backend 회귀 테스트를 보강한다.
- [x] 관련 테스트와 boundary/migration 검증을 실행한다.

## 검증
- frontend 관련 Vitest를 실행해 line-dashboard context와 surface 입력을 확인한다.
- Docker Compose `api` 컨테이너에서 assistant 및 drone 대상 테스트를 실행한다.
- Docker Compose `api` 컨테이너에서 migration 변경 없음과 backend boundary를 확인한다.
- frontend boundary audit를 실행한다.

## 위험과 대응
- 위험: 필터 기본값 차이로 history snapshot 범위가 달라질 수 있다.
- 대응: status에만 현재 필터를 명시하고 history는 기존 직접 라인 기준을 유지한다.
- 위험: 최근 시간 범위가 날짜 범위와 결합될 때 결과가 과도하게 좁아질 수 있다.
- 대응: 표 API와 동일한 시간 계산 규칙을 재사용하고 테스트로 고정한다.

## 진행 기록
- 2026-08-15: ESOP status 표와 Assistant snapshot의 라인 범위 및 시간 필터 불일치를 확인했다.
- 2026-08-15: 현재 status 필터 전달, target 매핑 조회, 최근 시간 범위 적용을 구현했다.
- 2026-08-15: frontend 182개, Assistant 60개, Assistant/Drone 대상 26개 테스트와 build, boundary, UI, migration 검증이 통과했다.
- 2026-08-15: status/history 계약을 엄격히 분리하고 선택 필드·기본값 보정 등 불필요한 호환 분기를 제거했다.
- 2026-08-15: 정리 후 frontend 183개와 Assistant/Drone 66개 테스트, build, boundary, UI, system check, migration 검증이 통과했다.
