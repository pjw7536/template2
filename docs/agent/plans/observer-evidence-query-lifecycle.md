# ExecPlan: Observer 근거 query 수명주기

## 목표
- AI 근거 링크로 Observer에 진입한 뒤 다른 호기로 전환하면 이전 근거 안내와 자동 선택 상태가 남지 않게 한다.
- 호기 전환 시 현재 날짜 범위와 AI 근거가 아닌 query는 유지한다.
- 과거 AI 근거 링크를 열면 resident log 보존 한도와 관계없이 해당 로그를 복원해 Data Log와 Log Detail에 표시한다.

## 현재 상태
- 근거 링크는 `evidenceId`, `analysisLogType`, `analysisTipGroup`을 query에 저장한다.
- 호기 변경 시 pathname만 바꾸고 `location.search` 전체를 유지해 이전 호기 근거 query가 새 호기에도 남는다.
- 관련 Observer hook과 테스트에는 사용자 작업 중인 필터 보존 변경이 있으므로 그대로 보존한다.
- 현재 근거 이동은 resident page를 순차 로드하며 찾다가 5,000건 보존 한도에 도달하면 중단하므로, 분석에 실제 사용된 근거도 복원하지 못할 수 있다.
- 기존 detail API는 source PK를 요구하지만 과거 evidence ID는 화면용 stable ID인 유형이 있어 단순 변환할 수 없다.

## 범위
- `observerEvidence`에 근거 전용 query 제거 유틸을 추가한다.
- `useObserverPageState`의 호기 pathname 전환에서만 해당 유틸을 적용한다.
- 유틸 및 호기 전환 회귀 테스트를 추가한다.
- 분석 근거 단건 복원 API와 frontend query hook을 추가한다.
- 복원한 근거를 resident 목록 앞에 고정하고 선택한 뒤 상세를 표시한다.
- DB schema, migration, 인증, 일반 날짜 범위 동기화는 변경하지 않는다.

## 설계
- 제거 대상은 `evidenceId`, 모든 `analysisLogType`, 모든 `analysisTipGroup`이다.
- `from`, `to`와 알 수 없는 다른 query는 보존한다.
- 현재 호기에서 날짜만 바꾸는 경로는 기존 search를 계속 사용한다.
- 근거 API는 `eqpId`, `evidenceId`, `from`, `to`를 검증하고 URL의 `log_key`에 대해 분석과 동일한 source filter로 최대 5,000건을 조회한 뒤 ID가 일치하는 한 건만 반환한다.
- resident 목록에 없는 근거는 Data Log 상단에 한 건만 추가하고 기존 목록과 ID로 중복 제거한다.
- 복원 API의 404와 기타 오류를 구분하고 기타 오류에는 재시도를 제공한다.
- public feature facade, migration, env, auth 영향은 없다.

## 실행 단계
- [x] 근거 query 제거 유틸과 단위 테스트를 추가한다.
- [x] 호기 전환 navigation에 제거 유틸을 적용한다.
- [x] 다른 호기 전환 시 안내가 해제되는 회귀 테스트를 추가한다.
- [x] Observer 테스트, ESLint, frontend boundary audit를 실행한다.
- [x] 분석 근거 ID를 동일 source 규칙으로 복원하는 selector와 API를 추가한다.
- [x] frontend 근거 단건 query hook을 추가하고 URL 설비 동기화 후에만 호출한다.
- [x] resident 밖 근거를 Data Log에 고정·선택하고 Log Detail에 표시한다.
- [x] loading/not-found/error 상태와 재시도 UI를 구분한다.
- [x] backend/frontend 테스트, ESLint, UI·boundary audit를 실행한다.

## 검증
- `npm run test:run --workspace web -- src/features/observer`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer`
- 대상 파일 ESLint
- `npm run agent:audit:web-boundary && npm run agent:audit:api-boundary && npm run agent:audit:ui`
- 기대 결과: 근거 링크는 resident 한도와 관계없이 해당 로그를 선택·표시하고, 호기를 사용자가 다시 변경하면 근거 query만 제거된다.

## 위험과 대응
- 위험: 날짜 범위나 향후 query까지 함께 삭제할 수 있다.
- 대응: 근거 전용 세 key만 명시적으로 삭제하고 보존 테스트를 둔다.
- 위험: 일반 전체 로그 API로 복원하면 분석용 EQP/TIP 사전 필터 차이로 근거가 누락될 수 있다.
- 대응: 분석 selector와 같은 필터·상한을 재사용하는 단건 API를 두고 일반 목록 API에 의존하지 않는다.
- 위험: 근거 식별자가 source 표시 ID와 source PK를 섞어 사용하는다.
- 대응: 분석 입력을 만든 공통 event ID 함수로만 비교한다.

## 진행 기록
- 2026-08-12: 호기 전환 시 근거 query만 제거하는 범위를 확정했다.
- 2026-08-12: Observer 테스트 33개, 대상 ESLint, frontend boundary audit와 diff check를 통과했다.
- 2026-08-12: resident page 탐색 대신 분석 동일 source 규칙을 사용하는 근거 단건 복원 API를 추가하는 것으로 설계를 갱신했다.
- 2026-08-12: 근거 단건 API, frontend query/pinning, 상태 UI를 구현했고 frontend 36개·backend 77개 테스트와 ESLint, UI·frontend·backend boundary audit, diff check를 통과했다.
