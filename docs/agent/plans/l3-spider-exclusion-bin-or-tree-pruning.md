# ExecPlan: L3 Spider 제외 필터 Bin OR와 빈 선택 트리 제거

## 목표
- 제외 필터의 `bin_name`에 쉼표로 입력한 여러 패턴을 OR 조건으로 적용한다.
- 활성 제외 필터 적용 후 High Risk leaf가 하나도 남지 않은 선택 패널 상위 분기를 제거한다.

## 현재 상태
- 제외 규칙은 각 필드를 단일 와일드카드 패턴으로 매칭한다.
- `filter-candidates`는 EQPCH/Bin leaf를 정확히 필터링하지만 Meta와 Structure는 경로 정보만 사용해 하위가 빈 상위 항목이 남을 수 있다.
- 활성 제외 필터가 있으면 `daily-summary`가 이미 해당 날짜 Parquet을 전량 읽어 행 단위 필터를 적용한다.

## 범위
- L3 Spider service의 `bin_name` 매칭 규칙과 daily summary 응답을 변경한다.
- Chart 선택 패널이 필터 적용 후의 선택 트리를 우선 사용하도록 변경한다.
- backend service 테스트와 frontend lint/build로 회귀를 검증한다.
- DB schema, migration, 권한 계약은 변경하지 않는다.

## 설계
- `bin_name`만 쉼표를 OR 구분자로 사용한다.
- 각 토큰은 trim하고 빈 토큰은 무시하며 기존 `*`, `%` 와일드카드를 그대로 지원한다.
- 필터링된 High Risk 행에서 `lineName/process/eds/step/ppid/eqc/bin` 중첩 트리를 생성한다.
- 필터가 없을 때는 `selectionTree=null`을 반환해 기존 고속 Meta/Structure/Candidate 경로를 유지한다.
- 필터가 있을 때는 daily summary의 `selectionTree`를 선택 패널의 source of truth로 사용한다.
- 다른 trellis leaf가 없는 상위 branch는 트리에 생성되지 않으므로 모든 상위 패널에서 자동으로 사라진다.
- 현재 선택이 새 트리에 없으면 해당 선택과 하위 선택을 정리한다.

## 실행 단계
- [x] 쉼표 OR 패턴 매칭과 테스트를 추가한다.
- [x] 필터링된 daily summary 행에서 selection tree를 생성한다.
- [x] frontend 선택 유틸과 DataSelector에 selection tree를 연결한다.
- [x] Step/PPID/EQPCH/Bin 후보가 selection tree를 사용하도록 연결한다.
- [x] 제외 필터 mutation이 daily summary까지 무효화하도록 보강한다.
- [x] backend 테스트와 frontend 검증을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- `cd apps/web && npm run lint`
- `cd apps/web && npm run build`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 필터가 없는 일반 조회까지 느려질 수 있다.
- 대응: `selectionTree` 생성은 기존에 Parquet을 읽는 활성 필터 경로에서만 수행한다.
- 위험: 선택 중인 branch가 필터 변경 후 화면에 보이지 않은 채 상태에 남을 수 있다.
- 대응: filtered tree 변경 시 현재 selection을 교집합으로 정리한다.
- 위험: Warning만 남은 branch가 숨겨질 수 있다.
- 대응: 현재 EQPCH/Bin 패널이 High Risk 후보만 표시하는 계약에 맞춰 High Risk leaf를 기준으로 트리를 만든다.

## 진행 기록
- 2026-07-15: 현재 제외 필터와 선택 후보 데이터 흐름을 확인하고 구현 방향을 확정했다.
- 2026-07-15: Bin Name 쉼표 OR, High Risk 선택 트리, 현재 선택 정리, 캐시 무효화를 구현했다.
- 2026-07-15: L3 Spider backend 54 tests, frontend lint/build, `git diff --check`를 통과했다. API boundary audit은 변경 범위 밖 `apps/api/api/observer/tests.py` 구문을 host Python 3.8이 파싱하지 못해 중단됐다.
