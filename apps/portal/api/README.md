# Django API 안내

`apps/portal/api`는 웹앱이 사용하는 Django API 서버입니다. 인증, 소속/권한, 메일, RAG/Assistant, Drone SOP, AppStore, VOC 같은 업무 API가 이 안에 있습니다.

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

| 파일 | 설명 |
| --- | --- |
| `local/portal/env/api.env`, `api-k8s.env` | 로컬 API 입력과 Kubernetes 차이 |
| `deploy/portal/env/prod/api.env`, `deploy/portal/env/test/api.env` | 운영·테스트 API 입력 |
| `local/portal/k8s` | 공통 base를 사용하는 로컬 Portal 구성 |
| `local/shared/compose/k8s-check.yml` | Django 검사용 일회성 api 서비스 |

기본 데이터베이스는 PostgreSQL입니다. Django 기본 DB는 `DJANGO_DB_*` 환경 변수를 사용합니다.

## 앱별 역할

| Django app | 역할 |
| --- | --- |
| `api.auth` | OIDC 로그인/로그아웃/현재 사용자 |
| `api.account` | 사용자 소속, 접근 권한, 사용자 pool |
| `api.emails` | 메일 수집/조회/이동/삭제/OCR/RAG Outbox |
| `api.assistant` | 사용자별 대화방 저장, OpenWebUI 일반 대화, 메일 RAG/LLM 답변 생성 |
| `api.rag` | RAG 서버 호출 공통 client |
| `api.drone` | Line Dashboard와 Drone SOP 알림 파이프라인 |
| `api.observer` | 기본 DB 기준정보/로그 조회 |
| `api.appstore` | 내부 앱 등록, 댓글, 좋아요 |
| `api.activity` | ActivityLog 조회 |
| `api.voc` | VOC 게시글/답변 |
| `api.common` | 공통 middleware, DB, storage, mail, messenger helper |
| `api.health` | health check |

## 자주 쓰는 관리 명령

`ensure_dev_database`, `process_email_outbox`는 준비된 로컬 환경에서 아래 형태로 실행합니다(저장소 루트 기준).

```bash
docker compose --project-name tailwind-k8s-check --env-file local/shared/runtime/db.env -f local/shared/compose/k8s-check.yml run --rm -T api <command>
```

## 더 읽을 문서

- 전체 구조: `docs/architecture.md`
- 백엔드 상세 구조: `docs/backend.md`
- 실제 API route/model/command 색인: `docs/inventory.md`
- 데이터 모델: `docs/data-model.md`
- 환경 설정: `docs/configuration.md`
- API 공통 규칙: `docs/api/README.md`
- 모듈별 API 계약: `docs/api/*.md`
- 모듈별 기능/동작: `docs/modules/*.md`
- 운영/외부 연동: `docs/operations.md`, `docs/integrations.md`
