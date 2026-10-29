# 백엔드 상세 구조

[문서 홈](../README.md) · [첫 셋업](../getting-started/01-setup.md) · [자주 쓰는 명령](../getting-started/02-usage.md)

API는 화면·Airflow 등이 보낸 요청의 인증과 입력을 검사하고, 업무 데이터를 조회하거나 변경합니다.
메일·계정 같은 업무는 `api.<feature>` Django app으로 묶습니다.
각 app 안에서 HTTP 처리(view), 읽기(selector), 쓰기·외부 호출(service)의 책임을 나눕니다.

소스는 `apps/portal/api`에 있으며, 전체 URL 연결은 `apps/portal/api/api/urls.py`가 담당합니다.
처음 보는 용어는 [용어 안내](../concepts/04-glossary.md)를 참고하세요.

## API 하나를 수정하는 순서

1. [API 명세](../api/README.md)에서 입력·응답·권한·부작용을 확인합니다.
2. [구현 색인](../reference/02-inventory.md#백엔드-api-route)에서 대상 app과 `urls.py`를 찾습니다.
3. URL이 연결하는 view에서 selector·service·model을 따라가며 변경할 책임을 정합니다.
4. 업무 로직을 수정하면 해당 service·selector 중심으로 검증하고 API 응답·권한을 확인합니다.
5. [API 실행 안내](../../apps/portal/api/README.md#실행하기)에 따라 소스가 포함된 검사 이미지를 갱신하고 검사를 실행합니다.

DB 구조가 바뀌면 migration을 추가합니다. 운영 DB 적용은 [migration 안내](03-migration-guide.md)를 따릅니다.
개발 명령은 [테스트·migration 스킬](../../.codex/skills/django-test-migration-flow/SKILL.md)에 있는 Compose `api` 실행 절차를 사용합니다.

## 실행 단위

| 항목 | 값 |
| --- | --- |
| 프레임워크 | Django 5.2 이상·6.0 미만, Django REST Framework |
| 기본 API 경로 접두사 | `/api/v1/` |
| 로그인 callback 예외 | `/auth/keycloak/callback/` |
| 기본 DB | `DJANGO_DB_*` PostgreSQL |
| 로컬 실행 | `make dev` (전체 Kubernetes) |

## App 구조

| App | 책임 | 주요 파일 |
| --- | --- | --- |
| `api.auth` | OIDC 인증, 로그인/로그아웃, 현재 사용자 | `views.py`, `callback_urls.py`, `services/oidc*.py` |
| `api.account` | 사용자 검색, Keycloak 세션의 소속·접근 권한 조회 | `models.py`, `selectors/`, `services/*.py`, `views/` |
| `api.emails` | 메일함, 메일 수집, asset, OCR, RAG Outbox | `models.py`, `permissions.py`, `services/*.py`, `management/commands/*.py` |
| `api.data_movement` | 파일 기반 DB 적재 trigger와 테이블별 loader | `urls.py`, `views.py`, `<table_name>/models.py`, `<table_name>/services/*.py`, `<table_name>/management/commands/*.py` |
| `api.assistant` | 대화방 영구 저장, RAG 검색, OpenWebUI/LLM 호출, 답변 조립 | `services/conversations.py`, `services/chat.py`, `services/rag.py`, `services/llm.py` |
| `api.rag` | RAG 공통 client와 설정 | `services/client.py`, `services/config.py` |
| `api.drone` | Drone SOP 수집, 알림 대상, dispatch/delivery, 라인 대시보드 | `models.py`, `selectors/`, `services/*.py`, `management/commands/*.py` |
| `api.observer` | 기본 DB 기준 정보/로그 조회 | `selectors/`, `views/` |
| `api.appstore` | 내부 앱, 댓글, 좋아요, cover | `models.py`, `services/*.py`, `views/` |
| `api.voc` | VOC 게시글과 답변 | `models.py`, `services/posts.py`, `views.py` |
| `api.activity` | 활동 로그·앱 접속 통계·외부 사용량 동기화 | `models.py`, `selectors.py`, `services/recording.py`, `services/` |
| `api.health` | health check | `services/health_status.py`, `views.py` |
| `api.common` | 공통 DB, storage, mail, messenger, request helper | `services/*.py` |

## 책임 분리

| 계층 | 책임 | 금지/주의 |
| --- | --- | --- |
| `urls.py` | 상대 route 선언 | 비즈니스 로직 금지 |
| `views.py` | 인증 확인, request 파싱, serializer/selector/service 호출, response 변환 | 복잡한 ORM 읽기/쓰기 직접 구현 금지 |
| `serializers.py` | 입력 검증, 출력 schema | 외부 호출/DB write 금지 |
| `selectors.py` | read-only ORM query, 외부 read-only DB 조회 | side effect 금지 |
| `services/` | 쓰기, transaction, 외부 호출, orchestration | HTTP request/response 객체 의존 최소화 |
| `models.py` | schema, 제약, 순수 domain helper | 외부 시스템 호출 금지 |
| `management/commands/` | 운영/개발 command entry | 다른 feature 내부 module 직접 우회 금지 |

단순한 app은 `views.py`, `selectors.py`, `serializers.py`, `tests.py`처럼 단일 파일을 사용할 수 있습니다.
책임을 나눠야 하면 같은 이름의 패키지로 전환합니다. `services/__init__.py`와
`selectors/__init__.py`는 외부에 공개할 이름을 명시적으로 다시 내보내며 실행 로직을 넣지 않습니다.

## URL prefix

| Prefix | App | 문서 |
| --- | --- | --- |
| `/api/v1/auth/` | `api.auth` | [Auth API](../api/01-auth.md) |
| `/api/v1/account/` | `api.account` | [Account API](../api/02-account.md) |
| `/api/v1/emails/` | `api.emails` | [Emails API](../api/03-emails.md) |
| `/api/v1/data-movement/` | `api.data_movement` | [Data Movement API](../api/14-data-movement.md) |
| `/api/v1/assistant/` | `api.assistant` | [Assistant API](../api/04-assistant.md) |
| `/api/v1/line-dashboard/` | `api.drone` | [Line Dashboard / Drone API](../api/05-line-dashboard.md) |
| `/api/v1/l3_spider/` | `api.l3_spider` | [L3 Spider API](../api/08-l3-spider.md) |
| `/api/v1/l0_spider/`, `/api/v1/fdc-trend/` | `api.l0_spider` | [L0 Spider API](../api/07-l0-spider.md) |
| `/api/v1/pm_spider/` | `api.pm_comparison` | [PM SPIDER API](../api/09-pm-spider.md) |
| `/api/v1/tttm_spider/` | `api.tttm_spider` | [TTTM Spider API](../api/10-tttm-spider.md) |
| `/api/v1/observer/` | `api.observer` | [Observer API](../api/06-observer.md) |
| `/api/v1/appstore/` | `api.appstore` | [AppStore API](../api/11-appstore.md) |
| `/api/v1/voc/` | `api.voc` | [VOC API](../api/12-voc.md) |
| `/api/v1/activity/` | `api.activity` | [Activity / Health API](../api/13-activity-health.md) |
| `/api/v1/health/` | `api.health` | [Activity / Health API](../api/13-activity-health.md) |

## 인증과 권한 기준

| 방식 | 사용 위치 | 확인 값 |
| --- | --- | --- |
| Django session | 일반 브라우저 API | 로그인 세션 쿠키 |
| OIDC callback | `/auth/keycloak/callback/` | Keycloak authorization code + PKCE, JWKS 검증 |
| Airflow Bearer token | 수집/동기화 trigger | `Authorization: Bearer <AIRFLOW_TRIGGER_TOKEN>` |
| Internal OCR token | OCR worker | `X-Internal-Token: <EMAIL_OCR_INTERNAL_TOKEN>` |
| 공개 | Auth 설정·로그인, health | 업무 조회 API는 세션·앱 접근 검사. 세부 조건은 endpoint별 문서 확인 |

## Management command

웹 요청 없이 실행하는 업무·운영 명령은 해당 app의 `management/commands/`가 소유합니다.
명령 전체 목록과 옵션·파일 마운트 예시는 [Django 관리 명령](../reference/03-operations.md#django-관리-명령)에 있습니다.
명령 이름으로 실제 파일을 찾을 때는 [구현 색인](../reference/02-inventory.md)을 사용합니다.

개발 backend 명령과 feature test는 Docker Compose `api` 컨테이너에서 실행합니다.
PR CI와 전체 회귀 검증은 외부 연결이 차단된 `deploy/portal/compose/test.yml`의 `api-test`를 사용합니다.
검사·명령의 실행 환경과 데이터 변경 여부를 확인한 뒤 필요한 명령만 실행합니다.

## 변경 시 갱신해야 하는 문서

- route 추가/변경: `docs/reference/02-inventory.md`, `docs/api/*.md`, `docs/modules/*.md`
- model/schema 변경: `docs/concepts/02-data-model.md`, 해당 `docs/modules/*.md`
- env contract 변경: `docs/reference/01-configuration.md`, `docs/concepts/03-integrations.md`, 필요 시 `local/adfs_dummy`
- command 추가/변경: `docs/reference/02-inventory.md`, `docs/reference/03-operations.md`
