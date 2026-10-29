# Django API 안내

`apps/portal/api`는 웹앱이 사용하는 Django API 서버입니다. 인증, 소속/권한, 메일, RAG/Assistant, Drone SOP, AppStore, VOC 같은 업무 API가 이 안에 있습니다.

처음 실행한다면 [첫 셋업 가이드](../../../docs/getting-started/01-setup.md)에서 도구·chart를 먼저 준비합니다.

## 실행하기

에이전트는 이 폴더 또는 상위 Portal에서 시작합니다. [Portal 지침](../AGENTS.md)과
[API 지침](AGENTS.md)을 적용하고 `api/<feature>`부터 탐색합니다.
로컬 앱은 Kubernetes에서 실행하고 Django 검사·명령은 일회성 Docker Compose `api` 컨테이너에서 실행합니다.
아래 명령은 저장소 루트 기준이며 이 폴더에서는 `make -C ../../.. <target>`을 사용합니다.

```bash
make dev
make check-api
make test-api
```

`make dev`는 전체 로컬 앱을 기동합니다. 준비된 환경에서 API 소스 변경 후에는
`make k8s-rebuild APP=portal`로 검사할 이미지를 갱신합니다.
마이그레이션 누락 여부를 확인할 때:

```bash
make makemigrations-check
```

특정 feature 테스트·migration 생성은 [테스트 스킬](../../../.codex/skills/django-test-migration-flow/SKILL.md)을 따릅니다.
검사 이미지는 소스를 내장하며 migration 생성 파일을 보존하려면 스킬의 소스 마운트 명령을 사용합니다.

## 설정 파일

아래 경로는 모두 저장소 루트를 기준으로 합니다.

| 파일 | 설명 |
| --- | --- |
| `local/portal/env/api.env`, `api-k8s.env` | 로컬 API 입력과 Kubernetes 차이 |
| `deploy/portal/env/prod/api.env`, `deploy/portal/env/test/api.env` | 운영·테스트 API 입력 |
| `local/portal/k8s` | 공통 base를 사용하는 로컬 Portal 구성 |
| `local/shared/compose/k8s-check.yml` | Django 검사용 일회성 api 서비스 |

기본 데이터베이스는 PostgreSQL입니다. Django 기본 DB는 `DJANGO_DB_*` 환경 변수를 사용합니다.

## 업무 코드 찾기

대상 app의 `urls.py`에서 view를 찾고, view가 호출하는 selector·service·model을 따라갑니다.
계층별 역할과 app 목록은 [API 개발 설명](../../../docs/development/02-backend.md)에,
정확한 endpoint·모델 이름은 [구현 색인](../../../docs/reference/02-inventory.md)에 있습니다.

## 자주 쓰는 관리 명령

`ensure_dev_database`는 개발 DB를 준비하고, `process_email_outbox`는 이메일 Outbox를 처리합니다.
준비된 로컬 환경에서 아래 명령으로 관리 명령 목록을 확인합니다(저장소 루트 기준).

```bash
docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env -f local/shared/compose/k8s-check.yml run --rm -T api help
```

실행할 때는 마지막 `help`를 필요한 명령과 옵션으로 바꿉니다. 예를 들어 `help process_email_outbox`는 해당 명령의 사용법을 보여줍니다.

## 더 읽을 문서

- [전체 구조](../../../docs/concepts/01-architecture.md)
- [백엔드 상세 구조](../../../docs/development/02-backend.md)
- [실제 API route·model·command 색인](../../../docs/reference/02-inventory.md)
- [데이터 모델](../../../docs/concepts/02-data-model.md)과 [환경 설정](../../../docs/reference/01-configuration.md)
- [API 공통 규칙과 모듈별 호출 계약](../../../docs/api/README.md)
- [모듈별 기능과 동작](../../../docs/modules/README.md)
- [운영 절차](../../../docs/reference/03-operations.md)와 [외부 연동](../../../docs/concepts/03-integrations.md)
