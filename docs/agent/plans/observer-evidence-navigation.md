# ExecPlan: Observer AI 근거 로그 이동

## 목표
- Assistant의 Observer 분석 근거를 클릭하면 분석 당시 조회 조건을 복원하고 해당 로그를 찾아 강조한다.
- 분석 당시 범위와 현재 조회 범위를 구분하고 실제 모델명·프롬프트 버전을 저장·표시한다.

## 현재 상태
- Observer 분석 응답은 scope, coverage, finding별 evidence ID를 반환한다.
- Assistant context snapshot은 scope·coverage·evidence를 제한된 JSON으로 저장한다.
- Observer 테이블과 timeline은 공통 selection store로 선택 행을 동기화한다.
- 로그는 유형별 cursor pagination으로 최대 resident 한도까지 추가 조회할 수 있다.

## 범위
- 수정: Observer 분석 metadata, Observer evidence URL 유틸·조회 복원·행 선택, Assistant 근거 패널, 관련 테스트·문서.
- 제외: 새 DB 컬럼·migration, 원본 로그 복제, 분석 재실행, 모바일 전용 UI.

## 설계
- Observer 분석 서비스는 `analysisModel`, `promptVersion`, `schemaVersion`을 meta에 포함한다.
- frontend snapshot의 각 evidence target에 분석 scope를 포함한 `/observer/<eqpId>` 링크를 저장한다.
- Observer page는 링크의 from/to, logTypes, tipGroups, evidenceId를 읽어 filter를 복원한다.
- 현재 resident 데이터에 근거가 없으면 해당 로그 유형의 다음 cursor를 순차 요청하고, 발견 시 selection source를 `assistant`로 지정한다.
- Assistant 근거 패널은 분석 당시 범위, 현재 범위 일치 여부, 모델·프롬프트 버전과 근거 이동 버튼을 표시한다.

## 실행 단계
- [x] 분석 버전 metadata와 유효 evidence ID 정규화를 구현한다.
- [x] evidence URL 생성·해석·로그 ID 매칭 유틸과 테스트를 추가한다.
- [x] Observer scope 복원·pagination 탐색·선택 강조를 연결한다.
- [x] Assistant 근거 패널에 범위 비교·버전·근거 버튼을 적용한다.
- [x] backend/frontend 테스트, lint/build, 경계·UI·문서 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.observer api.assistant --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `npm --prefix apps/web run test:run`
- `npm run web:lint`, production build, frontend/backend/UI/docs audit

## 위험과 대응
- 위험: 근거 로그가 첫 page에 없을 수 있다.
- 대응: 근거 로그 유형만 cursor로 순차 조회하고 resident 한도 도달 시 명확한 실패 상태를 표시한다.
- 위험: 모델이 입력에 없는 evidence ID를 생성할 수 있다.
- 대응: backend가 실제 분석 context에 포함된 ID만 응답에 남긴다.
- 위험: 과거 분석 scope와 현재 지원 조회 기간이 다를 수 있다.
- 대응: 기존 최대 90일 범위 정규화를 재사용하고 화면에서 복원 여부를 표시한다.

## 진행 기록
- 2026-08-11: 사용자가 추가 개선 중 Observer 근거 상세 연결만 우선 진행하도록 결정했다.
- 2026-08-11: 유효 근거 ID 필터, 분석 버전 metadata, 범위 복원 URL, 자동 cursor 탐색·행 강조, ChatWidget 근거 패널을 구현하고 대상 테스트를 통과했다.
- 2026-08-11: backend 106개·frontend 109개 테스트, lint, migration check, 임시 경로 production build, boundary/UI/docs audit를 통과했다. 기본 dist build는 기존 산출물 소유권 때문에 임시 경로로 대체 검증했다.
