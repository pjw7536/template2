# ExecPlan: Portal Assistant 앱 컨텍스트 통합

## 목표
- 모든 앱에서 같은 Portal Assistant 대화방과 기억을 이어서 사용합니다.
- 앱 이동 시 대화 로직을 교체하지 않고 현재 앱의 고정 배경지식 또는 화면 전용 데이터를 요청에 결합합니다.
- 앱 또는 화면 전환 안내 구분선을 제거하고 현재 연결된 앱 배경지식을 위젯에서 명확히 표시합니다.

## 현재 상태
- `ChatWidget`은 일반 화면에서 OpenWebUI를 사용하지만 Emails와 Observer는 별도 sender/context key를 사용합니다.
- 일반 Chat과 Observer만 `chatwidget:shared` rolling summary를 공유하며 Email RAG는 분리되어 있습니다.
- `ChatMessages`는 context key 변경마다 "현재 화면이 변경되었습니다" 구분선을 표시합니다.

## 범위
- 프런트엔드 경로별 앱 컨텍스트 해석, Assistant 기억 키, 위젯 상태 표시를 수정합니다.
- 백엔드 Assistant 기억 그룹과 OpenWebUI system message의 앱별 고정 배경지식을 수정합니다.
- Assistant 프런트엔드 및 Django 테스트를 갱신합니다.
- DB schema는 유지하고 기존 rolling summary cache만 초기화하는 data migration을 추가합니다.
- auth/permission, 외부 URL/env 계약은 변경하지 않습니다.

## 설계
- 경로는 프런트엔드의 고정 카탈로그에서 `appKey`, label, description으로 해석합니다.
- 일반 앱은 `assistant:openwebui:<appKey>` context key를 사용하고, 서버는 해당 접두사를 모두 `chatwidget:shared` 기억으로 해석합니다.
- Email RAG의 `assistant`, Observer의 `observer:*`, 일반 앱의 `assistant:openwebui:*`를 같은 기억 그룹으로 묶되, 현재 요청의 sender와 배경지식만 활성 앱 기준으로 선택합니다.
- OpenWebUI 앱 배경지식은 클라이언트 문자열을 신뢰하지 않고 서버 카탈로그가 context key에서 해석해 system message에 추가합니다.
- DB schema와 공개 endpoint 경로는 유지하고 기존 `contextKey` 계약을 확장 해석합니다.
- 기존 `assistant`와 `chatwidget:shared` summary row는 통합 후 count 기준이 달라지므로 data migration에서 삭제하고 원본 메시지로 재생성합니다.

## 실행 단계
- [x] 앱 경로/컨텍스트 카탈로그와 단위 테스트를 추가합니다.
- [x] ChatWidget과 대화 기억 필터가 앱 전환을 공유 기억으로 처리하도록 수정합니다.
- [x] 전환 구분선을 제거하고 활성 앱 배경지식 상태를 표시합니다.
- [x] Django 기억 해석 및 OpenWebUI 앱 배경지식 주입을 구현합니다.
- [x] 프런트엔드/백엔드 테스트와 경계·UI 감사를 실행합니다.
- [x] 전환 후 ChatWidget 참조 그래프와 호환 경계를 코드리뷰합니다.
- [x] 미사용 상태·불필요한 JSX 래퍼·오래된 현재 문서와 테스트 표현을 정리합니다.
- [x] 정리 후 전체 회귀 테스트와 정적 감사를 다시 실행합니다.
- [x] 기존 `assistant`/`chatwidget:shared` rolling summary cache 초기화 migration과 회귀 테스트를 반영합니다.

## 검증
- `npm --prefix apps/web run test:run -- src/lib/assistant/appContext.test.js src/features/assistant/hooks/useChatSession.test.jsx src/features/assistant/components/ChatWidget.test.jsx src/features/assistant/components/ChatMessages.test.jsx`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate assistant 0002 --plan`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:ui`
- 기대 결과: 앱별 context key가 같은 대화 기억을 공유하고, OpenWebUI 요청에는 현재 앱의 서버 고정 배경지식만 포함되며 모든 검증이 통과합니다.

검증 결과:
- 프런트엔드 전체 테스트 180개가 통과했습니다.
- Django Assistant 테스트 49개가 `--keepdb`로 통과했고 `makemigrations --check --dry-run`에서 변경 없음이 확인됐습니다.
- `assistant.0002_reset_portal_assistant_summary_cache` migration plan과 삭제 범위 회귀 테스트가 통과했습니다.
- UI, frontend boundary, backend boundary 감사와 변경 파일 ESLint가 통과했습니다.
- 기본 `dist` 빌드는 기존 산출물 삭제 권한 때문에 중단됐지만, 임시 출력 디렉터리의 동일 production build는 통과했습니다.

## 위험과 대응
- 위험: 앱 이름을 클라이언트 입력으로 받아 system prompt injection이 발생할 수 있습니다.
- 대응: context key에서 허용된 앱 키만 추출하고 서버 고정 카탈로그 외 값은 Portal 기본 상태로 처리합니다.
- 위험: 기존 Email RAG 기억이 일반 Chat과 분리되어 있던 동작이 바뀝니다.
- 대응: 메시지 출처를 앱 이름으로 명시해 모델에 전달하고, 기존 사용자 소유권·앱 접근 권한은 변경하지 않습니다.
- 위험: 기존 `chatwidget:shared` 요약의 `message_count`는 Email 메시지가 제외된 집합의 위치이므로 통합 집합에서 그대로 재사용하면 요약 대상이 어긋납니다.
- 대응: 원본 메시지는 유지하고 재생성 가능한 기존 summary row만 초기화하는 data migration을 적용합니다.

## 진행 기록
- 2026-08-12: 기존 일반 Chat·Observer 공유 기억과 Email RAG 분리 구조를 확인하고 통합 설계를 확정했습니다.
- 2026-08-12: 모든 Portal 앱을 방 단위 공용 기억으로 통합하고 서버 허용 앱 배경지식 주입과 UI 상태 표시를 완료했습니다.
- 2026-08-12: 기존 위젯 숨김 예외에서 L3 Spider와 TTTM Spider를 제거해 모든 업무 앱에서 공용 Assistant를 열 수 있게 했습니다.
- 2026-08-12: 전체 테스트, production build, migration 점검과 UI·경계 감사를 완료했습니다.
- 2026-08-13: 전환 후 코드리뷰를 시작하고 기존 저장 메시지/API 호환 코드와 제거 가능한 내부 잔재를 분류했습니다.
- 2026-08-13: 화면 전환 구분선의 불필요한 Fragment, 미사용 drag 상태, 과거 분리 구조를 설명하던 현재 문서를 제거했습니다.
- 2026-08-13: 앱 이동 후 실패 요청·응답 저장 재시도가 원래 sender와 context를 유지하도록 보완하고 전체 회귀 검증을 완료했습니다.
- 2026-08-13: 중복 Email route 판별기, pagination 이전 API wrapper, 비스트리밍 OpenWebUI frontend helper와 stale 통합 문서를 제거하고 전체 회귀 검증을 완료했습니다.
- 2026-08-13: 기존 rolling summary의 count 기준이 통합 전후로 달라지는 데이터 호환 위험을 확인해 migration 결정을 보류했습니다.
- 2026-08-13: 사용자 확인에 따라 원본 메시지를 보존하고 기존 공유·Email summary cache만 초기화하기로 확정했습니다.
- 2026-08-13: `0002` data migration과 원본 메시지·다른 문맥 요약 보존 테스트를 추가하고 전체 회귀·정적 감사를 통과했습니다.
