# ExecPlan: L3 Spider 정상 분석 조합 세부 요약

## 목표
- 라인별 세부 요약에 `daily_run_stats`에는 있으나 이상 집계에는 없는 분석 조합을 0행으로 표시한다.
- `이상없음 제외`는 기본 체크 상태로 두고, 해제하면 정상 행의 모든 수치가 0으로 보이게 한다.

## 범위
- 수정: Daily Summary matrix의 line_name/process_id/eds_step 조합 보강.
- 수정: 세부 요약 정상 행 렌더링과 기본 필터 상태.
- 수정: L3 Spider 서비스 회귀 테스트.
- 유지: API 필드명, PostgreSQL/SQLite source 선택, 차트 drill 동작, DB schema.

## 설계
- 이상 수치는 기존 `file_index`/Parquet 집계 결과를 우선한다.
- `daily_run_stats._details`를 제외 필터 적용 후 line_name/process_id/eds_step으로 축약한다.
- matrix에 없는 분석 조합만 Warning, High Risk, 이상 step_seq, 이상 EQPCH가 모두 0인 cell로 추가한다.
- matrix에 0행이 포함되어도 라인별 이상감지 요약의 활성 여부는 실제 Warning/High Risk 합계로 판단한다.

## 실행 단계
- [x] 분석 조합과 matrix cell 병합 helper 구현
- [x] 정상 조합 보강 회귀 테스트 추가
- [x] 세부 요약 기본 필터와 정상 수치 렌더링 변경
- [x] API·backend·frontend 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run l3_spider`
- `npm run web:build`
- L3 Spider 대상 파일 ESLint, frontend/backend boundary audit, UI audit
- 실제 dev mock 날짜의 Daily Summary HTTP 응답 확인

## 위험과 대응
- 위험: 0행을 matrix에 추가하면서 정상 라인이 이상 라인으로 표시될 수 있다.
- 대응: 프론트 활성 라인 목록을 matrix 존재 여부가 아니라 Warning/High Risk 합계로 계산한다.
- 위험: 제외된 step 조합이 0행으로 다시 나타날 수 있다.
- 대응: 기존 실행 통계 집계와 동일하게 `daily_run_stats._details`에도 제외 규칙을 먼저 적용한다.

## 진행 기록
- 2026-07-14: 세부 요약은 `matrix.cells`, 정상 분석 조합은 `daily_run_stats._details`에 존재하는 구조를 확인했다.
- 2026-07-14: 정상-only 회귀 테스트에서 모든 이상 수치가 0인 matrix cell 생성을 확인했다.
- 2026-07-14: L3 Spider 테스트 50개, Django check, migration check, 웹 빌드, ESLint, frontend/backend boundary audit를 통과했다.
- 2026-07-14: dev mock Daily Summary HTTP 200 응답과 기존 이상 cell 12개 유지를 확인했다.
- 2026-07-14: UI 감사는 기존 `L3SpiderChart.jsx` raw color/inline style 6건 때문에 실패했고 이번 변경 파일에는 신규 후보가 없다.
