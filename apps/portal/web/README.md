# Web SPA 안내

`apps/portal/web`은 React 19, React Router 7, Vite 6, Tailwind CSS 4로 만든 단일 페이지 웹앱(SPA)입니다.
서버 데이터는 React Query로 관리하고, Zustand는 화면 상호작용 같은 UI 상태에만 사용합니다.

## 실행하기

전체 앱을 처음 실행한다면 [첫 셋업 가이드](../../../docs/getting-started/01-setup.md)를 따릅니다.
`make dev`로 실행한 Portal의 기본 주소는 **http://localhost:8080**입니다.
이 환경에 Web 소스 변경을 반영하려면 `make k8s-rebuild APP=portal`을 실행합니다.

에이전트는 이 폴더 또는 상위 Portal에서 시작합니다. [Portal 지침](../AGENTS.md)과
[Web 지침](AGENTS.md)을 적용하고 `src/features/<feature>`부터 탐색합니다.
이 폴더에서 루트 Makefile을 호출할 때는 `make -C ../../.. <target>`을 사용합니다.

화면 개발용 Vite 서버를 따로 실행하려면 Node.js와 의존성을 준비합니다.
Web 개발·테스트에는 현재 lockfile 요구사항에 맞춰 Node.js 22.13 이상인 22.x를 사용합니다.

저장소 루트에서:

```bash
make web-install
make web-dev
```

`apps/portal/web` 안에서 직접:

```bash
npm ci --legacy-peer-deps
npm run dev
```

Vite 기본 주소는 `http://localhost:3000`이며 화면 소스 변경이 바로 반영됩니다.
이 명령은 API·DB·Keycloak을 기동하지 않습니다. API 기본 fallback은 `http://localhost:8000`이므로
kind API에 연결하려면 `VITE_BACKEND_URL=http://localhost:8080 make web-dev`처럼 주소를 전달합니다.
3000 주소에서 로그인과 쓰기 요청까지 사용하려면 API의 CORS·CSRF·로그인 후 이동 허용 주소도 맞춰야 합니다.
현재 기본 통합 설정은 8080 주소 기준입니다. 설정 위치는 [환경 설정](../../../docs/reference/01-configuration.md)을 참고합니다.
Grafana port-forward도 3000을 사용하므로 동시에 실행할 때 포트를 확인합니다.

## 빌드와 린트

```bash
make web-build
make web-lint
```

`apps/portal/web` 안에서 직접 실행할 수도 있습니다.

```bash
npm run build
npm run lint
npm run preview
```

## 환경 변수

컨테이너 개발 입력은 `local/portal/env/web.env`, 운영 입력은 `deploy/portal/env/prod/web.env`에서 관리합니다.
호스트의 `make web-dev`는 이 파일을 자동으로 읽지 않습니다. Vite에는 실행 환경변수 또는
`apps/portal/web/.env.development.local`의 `VITE_*` 값으로 전달합니다.
로컬 Kubernetes의 Web overlay는 공개 주소를 8080 기준으로 덮어씁니다.
운영 컨테이너는 시작 시 env를 `/runtime-env.js`로 생성하므로 Web env 변경은 설정 적용과 컨테이너 재시작으로 반영합니다.

| 변수 | 설명 |
| --- | --- |
| `VITE_BACKEND_URL` | 브라우저에서 호출할 Django API 주소 |
| `BACKEND_API_URL` | 컨테이너 내부 API 주소 |
| `VITE_PORTAL_PMX_URL` | Portal PMx 외부 링크. 비어 있으면 숨김 |
| `VITE_PORTAL_MOSAIC_URL` | Portal MOSAIC 외부 링크. 비어 있으면 숨김 |
| `VITE_PORTAL_CONFLUENCE_URL` | Portal Confluence 외부 링크. 비어 있으면 숨김 |

## 코드 구조

| 경로 | 설명 |
| --- | --- |
| `src/components/ui` | shadcn/Radix 기반 UI primitive |
| `src/components/layout` | 전역 layout component |
| `src/components/common` | 여러 화면에서 쓰는 공통 component |
| `src/features/<feature>` | 기능별 page, component, hook, api, store |
| `src/lib` | API helper, auth facade, theme, query client |
| `src/routes/router.jsx` | 전역 route 조립 |

## 현재 feature

`src/features`의 화면을 다음과 같이 나눕니다. 실제 경로는 [화면 색인](../../../docs/reference/02-inventory.md#프론트엔드-route)을 확인합니다.

| Feature | 제공하는 화면·기능 |
| --- | --- |
| `auth` | Keycloak 로그인 진입 |
| `account` | 내 계정·세션 권한 조회, 관리자용 사용자 목록 |
| `access-stats` | 앱별 접속 통계 |
| `emails` | 메일함과 메일 처리 |
| `assistant` | OpenWebUI 대화, 메일 RAG, 화면별 ChatWidget |
| `line-dashboard` | ESOP 대시보드와 Drone SOP 알림 |
| `observer` | 설비·로그 조회, TIP 상태와 AI 분석 |
| `spider`, `l0-spider`, `l1-spider`, `l3-spider` | Spider 진입·임베드·분석 화면 |
| `pm-spider`, `tttm-spider` | PM 비교, TTTM score·파형 조회 |
| `appstore` | 내부 앱 목록·등록·댓글 |
| `voc` | VOC 게시판 |
| `home`, `errors`, `teamstaff` | 홈·오류·팀 구성원 화면 |

소속 변경·권한 승인은 Keycloak에서 관리합니다. Portal 화면은 현재 세션 정보를 조회하며,
세부 권한은 [Account 모듈](../../../docs/modules/02-account.md)을 따릅니다.

## 개발 규칙 요약

- feature 외부 공개는 `src/features/<feature>/index.js` named export만 사용합니다.
- feature 간 의존은 [Web 지침](AGENTS.md)에 명시된 방향과 공개 facade만 허용합니다.
- JSX 파일은 `.jsx`, 비 JSX 파일은 `.js`를 사용합니다.
- Tailwind와 design token을 우선 사용하고, 임의 HEX/inline style은 피합니다.

## 더 읽을 문서

- [앱 문서 홈](../../../docs/README.md)
- [프론트엔드 상세 구조](../../../docs/development/01-frontend.md)
- [실제 route 색인](../../../docs/reference/02-inventory.md)
- [API 호출 규칙](../../../docs/api/README.md)
- [모듈별 업무 흐름](../../../docs/modules/README.md)
