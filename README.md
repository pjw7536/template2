# Tailwind 프로젝트 안내

이 저장소는 직접 개발하는 Portal·Airflow 소스와 설치형 제품의 Kubernetes 배포 정의를 함께 관리합니다.
Portal은 React 웹앱과 Django API로 구성된 업무용 모듈형 모놀리스이며, 로컬 개발용 더미 외부 시스템은 `local/adfs_dummy`에 있습니다.

## 최상위 폴더

```text
apps/    개발하는 코드·저장소 검사 도구
data/   실행 데이터
deploy/ 서버 배포·공통 정의·CI 입력
docs/   설명·설계·운영 문서
local/  외부 PC 개발 환경
```

실행은 루트 Makefile을 사용합니다. [사용 안내](docs/usage.md), [로컬 Kubernetes](local/README.md),
[저장소 도구](apps/tooling/README.md)를 참고하세요.
Compose 설정은 `local/`과 `deploy/`에서만 관리하며 루트 연결 파일은 제거했습니다.
Node 의존성은 `apps/portal/web/node_modules`, `apps/tooling/node_modules`에 개별 설치합니다. 루트에는 숨김 도구 설정만 예외로 유지합니다.

## 앱별 파일 찾기

- Portal: [소스·개발·검증](apps/portal/README.md), [서버 배포](deploy/portal/README.md)
- Airflow: [소스·이미지·검증](apps/airflow/README.md), [서버 배포](deploy/airflow/README.md)
- 설치형 제품: Keycloak·FTP·Monitoring·Headlamp는 `deploy/<app>`에서 관리하며 별도 `apps` 소스를 두지 않습니다.
- 검사 도구는 `apps/tooling`, 로컬 mock은 `local/adfs_dummy`가 소유합니다.
- 파일 원본: `apps/<app>` 소스, `deploy/<app>` 배포·공통 정의, `local/<app>` 개발 설정
- 서버 기본 checkout은 소스를 제외하며 빌드가 필요할 때 `--with-source`를 사용합니다.

## 한눈에 보기

| 영역 | 경로 | 역할 |
| --- | --- | --- |
| Web | `apps/portal/web` | React 19 + Vite SPA |
| API | `apps/portal/api` | Django 5.1 API 서버 |
| Dummy 외부계 | `local/adfs_dummy` | 로컬 ADFS/RAG/LLM/메일/Jira 대체 서버 |
| Docs | `docs` | 앱 전체 기능/API/운영/연동 문서 |
| Env | `local/<app>/env`, `deploy/<app>/env` | 앱별 Kubernetes·로컬 개발 환경 변수 |
| Proxy | `deploy/portal/k8s/base/nginx.conf` | 로컬 통합 진입점 |

## 실행 기준

외부 PC는 `make dev`로 한 컴퓨터의 전체 Kubernetes 앱을 실행합니다.
사내 서버는 `deploy/<app>`의 Kubernetes·Helm 정의로 배포합니다.

```bash
make dev
make k8s-status
make k8s-smoke
```

Portal·Keycloak·Airflow·FTP·MinIO·모니터링·mock을 kind에서 실행하고 PostgreSQL만 별도 Docker로 구동합니다.
기존 DB는 변경하지 않으며 `make down`도 새 DB volume과 호스트 데이터를 보존합니다.
Portal은 http://localhost:8080, Keycloak은 http://localhost:8180,
Airflow는 http://localhost:8080/airflow 에서 접근합니다.
Grafana는 `make k8s-grafana`, Headlamp는 `make k8s-ui`로 연결합니다.

설정·계정·포트 변경·데이터 보존은 [로컬 실행 안내](local/README.md)를 참고하세요.
서버 구성은 [배포 안내](deploy/README.md)를 따릅니다. Compose는 로컬 DB·API 검사·CI에만 사용합니다.
로컬 Kustomize 집계는 `local/shared/k8s`이며 Portal·Keycloak·Headlamp·mock의 앱별 원본을 참조합니다.

## 자주 쓰는 명령

```bash
make web-dev
make web-build
make web-lint
make k8s-rebuild APP=portal
make k8s-rebuild APP=airflow
make check-api
make test-api
make makemigrations-check
make k8s-render
make k8s-up
make k8s-ui
make k8s-down
```

## 주요 API 영역

모든 업무 API는 `/api/v1/` 아래에 있습니다. OIDC 콜백은 기존 ADFS의
`/auth/google/callback/`과 Keycloak의 `/auth/keycloak/callback/`을 사용합니다.

| Prefix | 설명 |
| --- | --- |
| `/api/v1/auth/` | 로그인, 로그아웃, 현재 사용자 |
| `/api/v1/account/` | 소속, 접근 권한, 사용자 검색 |
| `/api/v1/emails/` | 메일함, 메일 조회/이동/삭제, OCR, RAG Outbox |
| `/api/v1/assistant/` | RAG 기반 채팅 |
| `/api/v1/line-dashboard/` | Drone SOP, 라인 대시보드, 알림 |
| `/api/v1/observer/` | 라인/설비/로그 조회 |
| `/api/v1/appstore/` | 내부 앱 등록/댓글/좋아요 |
| `/api/v1/activity/` | 활동 로그 조회 |
| `/api/v1/voc/` | VOC 게시글/답변 |
| `/api/v1/health/` | 서버 상태 확인 |

## 문서 읽는 순서

1. 문서 홈과 전체 읽기 순서는 `docs/README.md`를 봅니다.
2. 전체 구조와 데이터 흐름은 `docs/architecture.md`를 봅니다.
3. 실제 route/model/env 색인은 `docs/inventory.md`를 봅니다.
4. 백엔드 상세는 `docs/backend.md`, 프론트엔드 상세는 `docs/frontend.md`를 봅니다.
5. 데이터 모델은 `docs/data-model.md`, 환경 설정은 `docs/configuration.md`를 봅니다.
6. API 공통 규칙은 `docs/api/README.md`, 모듈별 호출 방식은 `docs/api/*.md`를 봅니다.
7. 모듈별 업무 흐름은 `docs/modules/*.md`를 봅니다.

## 작업할 때 지켜야 할 큰 원칙

- 프론트엔드는 feature 외부에서 `apps/portal/web/src/features/<feature>/index.js`만 import합니다.
- 백엔드는 다른 feature를 직접 파고들지 않고 selector 또는 service facade를 통해 의존합니다.
- 서버 데이터는 React Query가 기준이고, Zustand에는 UI 상태만 둡니다.
- 인증/RAG/assistant/mail 계약을 바꾸면 `local/portal/k8s`, `local/shared/scripts/k8s_config.py`, `local/portal/env/api.env`, `local/adfs_dummy`도 함께 맞춥니다.

앱별 배포 파일 위치는 [배포 안내](deploy/README.md)를 참고합니다.

외부 PC 개발은 [local 안내](local/README.md), 사내 서버 clone은 [선택 체크아웃 안내](deploy/SERVER_CHECKOUT.md)를 따릅니다.
