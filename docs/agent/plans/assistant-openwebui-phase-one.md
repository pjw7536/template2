# ExecPlan: Assistant OpenWebUI 1차 기능 보강

## 목표
- 사용자당 서버 생성 1개를 보장하고 생성 실패·중단 상태를 DB에 남긴다.
- 메시지 원본을 보존한 채 질문 편집과 답변 재생성 분기를 지원한다.
- 대화방 직접 이름 변경, 고정, 보관, 제목·메시지 통합 검색을 제공한다.
- Observer 분석 집계와 제한된 근거를 메시지 스냅샷으로 저장하고 다시 확인할 수 있게 한다.
- Assistant 답변 평가와 Markdown·Excel 호환 CSV 내보내기를 제공한다.

## 현재 상태
- Django `assistant` app이 대화방·메시지·contextKey별 rolling summary를 소유한다.
- React ChatWidget은 SSE, 중단, 실패 재시도, cursor pagination을 제공한다.
- 동시 생성 제한은 브라우저 메모리 기반이라 다중 탭을 막지 못한다.
- 메시지는 시간순 flat 구조이고 대화방 검색은 제목에만 적용된다.
- Observer 응답은 분석 결과와 coverage를 반환하지만 Assistant 메시지에는 표시 문자열만 저장된다.
- 관련 변경이 아직 커밋되지 않은 dirty worktree 위에 있으므로 기존 변경을 보존한다.

## 범위
- 수정: `apps/api/api/assistant`, `apps/web/src/features/assistant`, Observer Assistant 응답 adapter, 관련 문서·테스트.
- 제외: 연결 종료 후 백그라운드 생성 지속·SSE 재연결, 다중 모델, 공개 공유, 파일 Knowledge, 음성·이미지·코드 실행.

## 설계
- `AssistantGeneration`은 사용자·대화방·문맥·상태·lease를 저장하고 partial unique constraint로 활성 생성 하나만 허용한다.
- 생성 acquire/finalize API를 모든 Assistant sender 앞뒤에서 호출하며 만료된 lease는 실패 처리한다.
- `AssistantMessage.parent`와 `revision_of`, `AssistantConversation.current_message`로 현재 분기 경로를 표현한다.
- 기존 메시지는 data migration으로 시간순 parent chain을 만들고 마지막 메시지를 current leaf로 지정한다.
- 대화방 metadata에 `pinned_at`, `archived_at`을 추가하고 PATCH와 archive query를 제공한다.
- 검색은 소유자 범위 안에서 제목과 메시지 내용을 함께 조회한다. 초기 구현은 DB 호환 ORM 검색을 사용한다.
- Observer sender가 scope·coverage·finding evidence를 `contextSnapshot`으로 반환하고 Assistant 저장 서비스가 bounded JSON snapshot을 만든다.
- 답변 평가는 메시지별 one-to-one row로 upsert하며 export는 현재 분기 전체를 Markdown 또는 UTF-8 BOM CSV로 반환한다.

## 실행 단계
- [x] 생성·분기·대화방 metadata·스냅샷·평가 schema와 migration을 추가한다.
- [x] service/selector/serializer/API 계약과 backend 테스트를 구현한다.
- [x] frontend API와 `useChatSession` 생성 lock·편집·재생성 동작을 연결한다.
- [x] RoomList와 ChatMessages에 관리·평가·내보내기 UI를 추가한다.
- [x] Observer 분석 snapshot adapter와 근거 표시를 연결한다.
- [x] API/Observer/frontend 테스트, migration, lint/build, 경계/UI/offsite 검증을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant api.observer`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate assistant`
- `npm run test:run`, `npm run lint`, 임시 outDir production build
- `npm run agent:audit:api-boundary`, `npm run agent:audit:web-boundary`, `npm run agent:audit:ui`, `npm run agent:audit:docs`
- `docker compose -f docker-compose.dev.yml config --quiet`와 dummy/Nginx 설정 검사

## 위험과 대응
- 위험: 기존 flat 메시지에 parent가 없어 분기 조회가 누락될 수 있다.
- 대응: data migration과 selector fallback을 함께 두고 기존 대화 회귀 테스트를 추가한다.
- 위험: 브라우저 종료 시 활성 생성 row가 남을 수 있다.
- 대응: 짧은 lease와 다음 acquire 시 만료 실패 처리를 적용한다.
- 위험: Observer snapshot이 커질 수 있다.
- 대응: scope·coverage와 정규화된 evidence만 허용하고 개수·문자 길이를 제한한다.
- 위험: 보관/검색 추가가 기존 cursor 순서를 깨뜨릴 수 있다.
- 대응: cursor에 archived/search 조건을 포함하고 기존 기본 요청 계약을 유지한다.

## 진행 기록
- 2026-08-11: 사용자가 새로고침 후 백그라운드 재연결을 제외한 권장 1차안을 승인했다.
- 2026-08-11: migration 0003을 적용하고 backend 105개·frontend 105개 테스트, lint, production build, 경계·UI·문서·Compose 검증을 완료했다.
