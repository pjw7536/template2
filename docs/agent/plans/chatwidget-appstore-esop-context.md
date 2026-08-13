# ExecPlan: ChatWidget Appstore·ESOP 배경지식 연결

## 목표
- Appstore와 ESOP Dashboard에서 ChatWidget이 현재 화면 범위의 서버 조회 데이터를 근거로 답변한다.
- 앱별 권한이 회수되면 저장된 질문·답변·요약을 다시 노출하지 않는다.

## 현재 상태
- 두 route는 `assistant:openwebui:<app-key>` 문맥과 한 줄짜리 정적 설명을 사용한다.
- `portal-default` Profile에는 Tool이 없고 `assistant` scope만 요구한다.
- Email RAG와 Observer 분석에는 Profile, Tool allowlist, scoped memory, access requirement 재검증 패턴이 있다.

## 범위
- Appstore 앱 메타데이터의 제한된 읽기 전용 검색·요약
- ESOP line 상태와 기간별 이력의 제한된 읽기 전용 snapshot
- React 현재 화면 조건 등록, Assistant Profile/Runtime/권한/테스트/문서 갱신
- 알림 수신자, 연락처, 댓글, 관리자 설정, 쓰기 동작은 제외

## 설계
- Appstore와 ESOP에 독립 Profile과 Tool을 부여하고 각각 `assistant`와 대상 앱 scope를 요구한다.
- frontend는 원본 데이터를 보내지 않고 검색·line·기간·화면 종류 같은 조회 조건만 보낸다.
- backend는 도메인 selector를 통해 데이터를 다시 조회하고 크기 제한된 snapshot을 OpenWebUI system context에 결합한다.
- 앱별 기억은 `scope:appstore`, `scope:line-dashboard`에 저장하고 현재 권한으로 매번 재검증한다.
- DB schema와 외부 RAG/OpenWebUI endpoint/env 계약은 변경하지 않는다.

## 실행 단계
- [x] Appstore·ESOP Assistant용 selector와 제한된 payload를 추가한다.
- [x] Assistant Profile, Tool 입력 정규화, Runtime 실행, context/access requirement를 확장한다.
- [x] Appstore·ESOP 화면 조건을 PageAssistantContext와 ChatWidget surface에 연결한다.
- [x] backend/frontend 회귀 테스트와 문서를 갱신한다.
- [x] Docker Compose backend 테스트와 frontend audit/test를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.appstore api.drone`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `cd apps/web && npm test -- --run src/features/appstore src/features/line-dashboard src/features/assistant src/lib/assistant`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`

## 위험과 대응
- 위험: 브라우저가 임의 line/검색 조건 또는 Tool을 주입할 수 있다.
- 대응: Profile allowlist, 서버 입력 정규화, 앱 scope 검증, 조회 범위/건수 제한을 적용한다.
- 위험: 대화 기억을 통해 권한이 없는 앱 데이터가 재노출될 수 있다.
- 대응: 앱별 memory partition과 저장된 `accountScopes`를 모든 재사용 시점에 검증한다.
- 위험: ESOP payload가 커져 prompt와 응답 지연이 증가할 수 있다.
- 대응: 집계 중심 snapshot과 고정된 기간·행·문자 제한을 적용한다.

## 진행 기록
- 2026-08-14: 권장 1차 범위와 hybrid static/live context 설계를 확정했다.
- 2026-08-14: Appstore 40개/설명 600자, ESOP 31일/최근 20행 상한과 개인정보 제외 규칙을 적용했다.
- 2026-08-14: 최종 backend 380개, frontend 117개 테스트와 migration check, lint, build, 전체 agent audit를 통과했다.
