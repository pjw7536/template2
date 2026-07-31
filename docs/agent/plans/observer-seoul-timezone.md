# ExecPlan: Observer Asia/Seoul 시간 기준 통일

## 목표
- Observer의 로그 조회 날짜 경계와 API 시간 응답, frontend 표시를 `Asia/Seoul` 기준으로 통일한다.
- 브라우저가 실행되는 지역이나 로그 유형에 따라 같은 시각이 다르게 보이지 않도록 한다.

## 현재 상태
- Django와 PostgreSQL session 기본 시간대는 UTC다.
- SPC/FDC Interlock 조회 경계만 `Asia/Seoul`을 명시하고 나머지 Observer 조회 경계는 UTC 기본값을 사용한다.
- frontend timeline과 Data Log는 브라우저 현지 시간으로 변환하고, 상세 화면은 offset을 제거한 문자열을 표시한다.
- EQP/TIP 원천 시간은 timezone이 없는 KST 벽시계 값이지만 loader가 PostgreSQL session의 UTC 값으로 저장한다.
- 기존 Log Detail은 offset을 제거해 원천 KST 벽시계와 같은 시간을 표시했고, Data Log는 저장된 값을 KST로 변환해 9시간 늦게 표시했다.

## 범위
- 수정할 영역:
  - `apps/api/api/observer`의 날짜 query 파싱, event time 직렬화, 테스트
  - `api.data_movement.eqp_status_chg`와 `api.data_movement.mi_tip_update_hist`의 원천 시간 해석, 기존 데이터 보정 migration, 테스트
  - `apps/web/src/features/observer`의 날짜 표시 유틸리티와 관련 테스트
  - Observer와 data movement API/module 문서
- 수정하지 않을 영역:
  - CTTTM/RACB/SPC/FDC/ESOP 원천 timestamp 적재 규칙
  - DB schema

## 설계
- 날짜-only 또는 offset 없는 Observer query는 `Asia/Seoul` 현지 시각으로 해석하고 `+09:00` ISO 문자열로 selector에 전달한다.
- aware datetime은 같은 instant를 `Asia/Seoul`로 변환한다.
- Observer API의 `eventTime`, `endTime`과 관련 상세 시간 필드는 `+09:00` offset을 포함한 문자열로 반환한다.
- frontend는 `Intl.DateTimeFormat`의 `Asia/Seoul` time zone을 사용하고 상세 시간도 같은 formatter를 거친다.
- EQP의 `chg_time`, `last_update_time`과 TIP의 `rule_pkg_update_date`, `gpm_update_date`, `last_update_date`는 timezone 없는 원천값을 `Asia/Seoul`로 해석해 UTC instant로 저장한다.
- 기존 EQP/TIP 시간값은 기존 Log Detail에 표시되던 벽시계를 기준으로 9시간 앞당기는 data migration으로 보정한다.
- public facade, auth, env, DB schema는 변경하지 않는다.

## 실행 단계
- [x] Backend query boundary와 event time 직렬화 helper를 추가한다.
- [x] compact/legacy/detail 응답에 Seoul 시간 직렬화를 적용한다.
- [x] frontend table/timeline/detail 표시를 Seoul 기준으로 고정한다.
- [x] backend 회귀 테스트와 frontend 교차 시간대 검증을 추가한다.
- [x] API/module 문서에 시간대 계약을 반영한다.
- [x] EQP/TIP loader가 timezone 없는 원천 시간을 `Asia/Seoul`로 해석하도록 수정한다.
- [x] 기존 EQP/TIP timestamp를 보정하는 data migration을 추가한다.
- [x] EQP/TIP loader 및 migration 회귀 검증을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.data_movement.eqp_status_chg api.data_movement.mi_tip_update_hist api.observer --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate eqp_status_chg`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate mi_tip_update_hist`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `TZ=Asia/Seoul`과 `TZ=America/Los_Angeles`에서 frontend formatter 출력 비교
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: 기존 cursor의 UTC/naive range key가 새 `+09:00` range key와 일치하지 않을 수 있다.
- 대응: cursor는 단기 opaque pagination token이므로 현재 조회 범위에서 다시 발급하며, scope 불일치는 기존과 같이 400으로 처리한다.
- 위험: 기존 대용량 EQP/TIP 테이블의 timestamp 일괄 갱신 중 row/index 갱신 비용과 잠금이 발생한다.
- 대응: 앱별 단일 data migration으로 범위를 제한하고 배포 시 각 migration 소요 시간과 DB 부하를 관찰한다.
- 위험: 기존 loader와 KST 해석 loader가 migration 전후에 동시에 적재하면 일부 row가 이중 보정되거나 기존 방식으로 남을 수 있다.
- 대응: EQP/TIP 적재를 중지하고 migration 적용, 신규 API 배포, 적재 재개 순서로 운영 반영한다.
- 위험: 실제 원천 시간이 일부 UTC였다면 일괄 9시간 보정이 해당 row를 잘못 변경한다.
- 대응: 사용자가 EQP/TIP 원천과 기존 Log Detail 시간을 KST 정답으로 확정한 계약에만 적용하고 다른 로그 유형은 변경하지 않는다.

## 진행 기록
- 2026-07-31: UTC/KST/browser-local 혼용 지점을 확인하고 표시·조회 기준을 `Asia/Seoul`로 통일하기로 했다.
- 2026-07-31: query boundary와 API 시간 응답을 `+09:00`으로 통일하고 frontend calendar·표·상세·timeline 축을 한국 시간으로 고정했다.
- 2026-07-31: Observer backend 테스트 56개, migration check, frontend lint/build, API/Web boundary audit, docs audit, 교차 시간대 formatter 검증이 통과했다.
- 2026-07-31: UI audit은 이번 변경과 무관한 기존 L3 Spider raw color와 Account/L3 Spider/Observer 측정용 inline style 후보를 보고해 종료 코드 1을 반환했다. 이번 변경 파일에서 새 UI 일관성 후보는 발생하지 않았다.
- 2026-07-31: 기존 EQP/TIP Log Detail의 벽시계가 원천 KST 정답이라는 사용자 확인에 따라 loader 시간 해석과 기존 데이터 보정을 범위에 추가했다.
- 2026-07-31: EQP/TIP loader 시간 해석과 retention 경계를 분리하고 기존 timestamp를 9시간 앞당기는 migration을 추가했다.
- 2026-07-31: EQP/TIP/Observer 테스트 75개, 대상 migration 적용과 SQL 확인, migration check, Django system check, API boundary audit, docs audit가 통과했다.
