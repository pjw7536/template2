# Portal API 개발 지침

## 작업별 진입점

`apps/portal/api/**`에 적용한다. 스킬 경로는 저장소 루트의 `.codex/skills/<name>/SKILL.md`다.

| 작업 | 스킬 |
| --- | --- |
| 새 도메인·인덱스/제약 이름 | `create-django-feature` |
| 업무 로직 테스트·migration | `django-test-migration-flow` |
| 도메인·조회/변경 경계 | `backend-boundary-audit` |
| 비자명한 Python 로직 설명 | `write-commented-python` |

## 허용 구조

- 도메인은 `api/<feature>` (`api.<feature>`)에 둔다. 허용 파일은 `__init__.py`, `apps.py`, `models.py`, `urls.py`, `views.py`, `serializers.py`, `selectors.py`, `permissions.py`, `admin.py`, `tests.py`다. `callback_urls.py`는 Auth 전용이다.
- 허용 폴더는 `services/`, `selectors/`, `views/`, `serializers/`, `tests/`, `migrations/`, `management/commands/`다. 기본 최대 깊이는 2이며 이 폴더들은 예외다. 승인되지 않은 백엔드 폴더를 새로 만들지 않는다.
- 공통·인프라 패키지는 `api.common`, `api.data_movement.common`, `api.auth`, `api.rag`, `api.management`만 사용한다.
- Data Movement의 테이블별 앱만 `api/data_movement/<table_name>` (`api.data_movement.<table_name>`) 중첩을 허용한다. 이름은 실제 테이블과 일치시키고 해당 테이블의 모델·migration·적재 서비스·테스트·명령만 소유한다. 공통 적재 도구는 `api/data_movement/common`에 둔다.

## 공개 경계와 책임

다른 도메인은 `services/__init__.py` facade 또는 `selectors.py`/`selectors/__init__.py` 공개면으로만 사용한다. 두 `__init__.py` 공개면에는 실행 로직 없이 명시적 re-export만 둔다. 테스트와 공통 명령도 다른 도메인 내부를 직접 import하지 않는다.

| 위치 | 책임 |
| --- | --- |
| views | HTTP·인증/권한·serializer·service/selector 호출·응답 |
| serializers / permissions | 스키마·입력 검증 / DRF 권한 검사 |
| services | 업무 로직·쓰기·트랜잭션·외부 호출 |
| selectors | 읽기 전용 ORM |
| models | 스키마·순수 도메인 규칙 |

- View·service의 읽기 ORM은 selector를 사용한다. Selector·model에는 쓰기를 두지 않는다.
- 여러 단계의 쓰기는 `transaction.atomic()`으로 묶는다. 공개 service·selector에는 타입 힌트와 한국어 docstring을 작성하고 단일 책임·선형 흐름을 유지한다.
- 도메인 전용 명령은 해당 앱에, 공통 명령은 공개 service·selector를 사용하는 공통 영역에 둔다.

## 라우팅과 DB

- 업무 API는 `/api/v1/<route-scope>/...`, Auth callback만 `/auth/` (`api.auth.callback_urls`)를 사용한다. 전역 `api/urls.py`는 include 목록만, feature `urls.py`는 상대 경로만 선언한다.
- 필드는 snake_case, 모델은 단수 PascalCase다. `db_table = "<feature>_<entity>"`, 기본키는 `id` (`BigAutoField`)를 사용한다. 외부 계약상 필요한 경우만 UUID를 쓴다.
- 시간은 시간대가 있는 UTC이며 `created_at` 필수, `updated_at`·`deleted_at`은 선택이다.
- 인덱스는 `idx_<table>_<cols>`, 제약은 `uniq_<table>_<cols>`를 기본으로 30자 이내에서 일관되게 축약한다. 약어·충돌 접미사 전체 규칙은 생성 스킬을 따른다.
- Data Movement 주 적재 모델의 `db_table`은 정확히 `<table_name>`이다. 보조 테이블은 `<table_name>_load_job`처럼 용도 접미사를 허용한다.

## 검증과 외부 연동

- 업무 로직 변경에는 테스트를 추가·갱신한다. Service·selector를 우선하고 view 테스트는 최소화한다. 적용된 migration을 수정하지 않는다.
- Django 테스트·명령은 Docker Compose `api` 컨테이너에서 실행한다. 이미지 갱신·test env·migration 파일 보존과 명령은 테스트 스킬을 따른다. Django를 실행하지 않는 정적 감사는 호스트에서 실행할 수 있다.
- 도메인 경계·import·view·selector 변경에는 `make audit-api-boundary`를 실행하거나 권고한다.
- Auth·RAG·Assistant·Mail 계약 변경은 상위 Portal 지침의 local 연결 조건과 `offsite-dev-contract-sync`를 따른다. 로컬 mock·개발 연결을 실행 가능한 상태로 유지한다.
