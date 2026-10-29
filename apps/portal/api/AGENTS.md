# Portal API 개발 지침

## 적용 범위

이 지침은 `apps/portal/api/**`에 적용합니다. 상위 [Portal 지침](../AGENTS.md)도 함께 따릅니다.

## 작업별 스킬

아래 경로는 저장소 루트 기준입니다. 현재 작업에 해당하는 스킬만 읽습니다.

| 작업 | 스킬 |
| --- | --- |
| 새 도메인 생성 | `.codex/skills/create-django-feature/SKILL.md` |
| 업무 로직 테스트·migration | `.codex/skills/django-test-migration-flow/SKILL.md` |
| 도메인 경계 검사 | `.codex/skills/backend-boundary-audit/SKILL.md` |
| Python 설명·주석 작성 | `.codex/skills/write-commented-python/SKILL.md` |

## 도메인 앱 구조

도메인 앱은 `apps/portal/api/api/<feature>`에 두며 Python 경로는 `api.<feature>`입니다.
다음 파일·폴더만 허용합니다.

- `apps.py`, `models.py`, `urls.py`, `callback_urls.py`(Auth 전용)
- `views.py`, `serializers.py`, `selectors.py`, `permissions.py`, `admin.py`, `tests.py`
- `services/`, `selectors/`, `views/`, `serializers/`, `tests/`, `migrations/`, `management/commands/`

승인된 경로 밖에 새 백엔드 폴더를 만들지 않습니다. 기본 최대 깊이는 2이며,
위의 `services/`·`selectors/`·`views/`·`serializers/`·`tests/`·`migrations/`·`management/commands/`는 예외입니다.

### Data Movement 예외

테이블별 앱만 중첩 도메인을 허용합니다.

- 경로: `apps/portal/api/api/data_movement/<table_name>` (`api.data_movement.<table_name>`)
- `<table_name>`은 실제 대상 테이블 이름과 일치해야 합니다.
- 각 앱은 해당 테이블의 모델·migration·적재 서비스·테스트·관리 명령만 소유합니다.
- 공통 적재 도구는 `apps/portal/api/api/data_movement/common`에 둡니다.

### 공통·인프라 패키지

다음 패키지만 공통·인프라 영역으로 사용합니다.

- `api.common`
- `api.data_movement.common`
- `api.auth`
- `api.rag`
- `api.management`

위 Python 경로는 모두 `apps/portal/api/api/` 아래에 대응합니다.

## 도메인 간 의존과 책임

다른 도메인은 해당 도메인의 `services/__init__.py` 공개 facade 또는 `selectors.py`로만 사용합니다.
`services/__init__.py`와 `selectors/__init__.py`에는 실행 로직 없이 명시적 re-export만 둡니다.

| 위치 | 담당하는 책임 |
| --- | --- |
| `views.py` | HTTP 처리만 수행 |
| `serializers.py` | 스키마와 입력 검증 |
| `permissions.py` | DRF 권한 검사 |
| `services/*` | 업무 로직·쓰기·트랜잭션·외부 호출 |
| `selectors.py` | 읽기 전용 ORM 조회 |
| `models.py` | 스키마와 순수 도메인 규칙 |

View와 service의 읽기 ORM 조회는 selector를 사용합니다. Selector와 model에는 쓰기를 두지 않습니다.

## 라우팅과 API 형식

- 업무 API는 `/api/v1/<route-scope>/...` prefix를 사용합니다.
- Auth callback만 `/auth/`를 사용합니다(`api.auth.callback_urls`).
- 전역 라우팅은 `apps/portal/api/api/urls.py`의 include 목록으로만 조립합니다.
- 각 feature의 `urls.py`는 상대 경로만 선언하며 업무 로직을 포함하지 않습니다.

## 모델과 DB 규칙

| 항목 | 규칙 |
| --- | --- |
| 필드 | `snake_case` |
| 모델 | 단수형 `PascalCase` |
| 테이블 | 모든 모델에 `db_table = "<feature>_<entity>"` 지정 |
| 기본키 | `id` (`BigAutoField`), 외부 계약상 필요한 경우에만 UUID |
| 시각 | 시간대가 있는 UTC. `created_at` 필수, `updated_at`·`deleted_at` 선택 |
| 인덱스 이름 | `idx_<table>_<cols>` |
| 제약 이름 | `uniq_<table>_<cols>` |

인덱스·제약 이름은 30자 이내로 만들고 일관된 축약·접미사 규칙을 적용합니다.
전체 명명 규칙은 `create-django-feature` 스킬을 따릅니다.
Data Movement의 주 적재 모델은 `db_table`을 정확히 `<table_name>`으로 지정하며,
보조 테이블에는 `<table_name>_load_job`처럼 용도를 나타내는 접미사를 붙일 수 있습니다.

## 안전성과 가독성

- 여러 단계의 쓰기는 `transaction.atomic()`으로 묶습니다.
- 명시적이고 선형적인 단일 책임 코드를 작성합니다.
- 함수·클래스는 실용적인 범위에서 작게 유지합니다(약 30~50줄).
- 공개 service·selector에는 타입 힌트와 한국어 docstring을 작성합니다.

## 테스트와 migration

- 업무 로직을 바꾸면 테스트를 추가하거나 갱신합니다. Service·selector 테스트를 우선하고 view 테스트는 최소화합니다.
- 적용된 migration은 수정하지 않습니다.
- 테스트에서 다른 도메인의 내부 모듈을 직접 import하지 않습니다.
- 도메인 전용 명령은 해당 앱에 두고, 공통 명령은 service·selector facade만 사용합니다.
- 백엔드 테스트·명령은 Docker Compose `api` 컨테이너에서 실행합니다.
- Django 런타임을 실행하지 않는 정적 에이전트 감사 스크립트는 호스트에서 실행할 수 있습니다.
- 도메인 경계·import·view·selector를 바꾸면 `make audit-api-boundary`를 실행하거나 권고합니다.

실행 순서와 명령은 `django-test-migration-flow` 스킬을 따릅니다.

## 외부 PC 개발

사내망 연결을 전제하지 않습니다. 사내 URL을 하드코딩하지 않고 외부 서비스 URL은 env로 주입합니다.
Auth·RAG·Assistant·Mail 계약 변경 시 로컬 mock·개발 연결도 실행 가능한 상태로 유지합니다.
세부 절차는 `offsite-dev-contract-sync` 스킬을 따릅니다.
