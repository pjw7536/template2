# 프론트엔드 상세 구조

[문서 홈](../README.md) · [첫 셋업](../getting-started/01-setup.md) · [자주 쓰는 명령](../getting-started/02-usage.md)

Web은 사용자가 보는 화면과 조작을 담당합니다. 화면별 코드는 메일·계정 같은 업무 기능(feature)으로 묶습니다.
화면을 바꿀 때는 해당 기능의 page에서 시작해 필요한 component·hook·API client를 따라갑니다.
서버 데이터는 React Query가, 선택 행·열린 패널 같은 UI 상태는 컴포넌트나 기능 내부 Zustand가 관리합니다.

구현에는 React 19·React Router 7·Vite 6·Tailwind CSS 4를 사용합니다.
처음 보는 용어는 [용어 안내](../concepts/04-glossary.md)를 참고하세요.

## 화면 하나를 수정하는 순서

1. [화면 색인](../reference/02-inventory.md#프론트엔드-route)에서 URL에 대응하는 기능을 찾습니다.
2. `apps/portal/web/src/features/<feature>/routes.jsx`에서 page를 찾고 UI·hook·API 호출을 확인합니다.
3. 서버 요청을 바꾼다면 [해당 API 명세](../api/README.md)를 확인합니다.
4. [Web 실행 안내](../../apps/portal/web/README.md#실행하기)에서 통합 환경 또는 Vite 개발 서버를 선택합니다.
5. [영역별 검사](../getting-started/02-usage.md#변경-영역별-검사)를 실행한 뒤 로딩·빈 결과·오류와 권한별 동작을 확인합니다.

통합 환경은 소스가 이미지에 포함되므로 수정 후 Portal 이미지를 갱신합니다.
Vite는 화면 변경을 바로 반영하지만 API·로그인 연결 설정이 별도로 필요합니다.

## 실행 단위

| 항목 | 값 |
| --- | --- |
| 프레임워크 | React 19, React Router 7 |
| 빌드 | Vite 6 |
| 스타일 | Tailwind CSS 4, shadcn/Radix 기본 UI 요소 |
| 서버 데이터 | React Query |
| UI 상태 | Zustand 또는 컴포넌트 상태 |
| 로컬 실행 | `make web-dev` |

## 최상위 구조

| 경로 | 역할 |
| --- | --- |
| `apps/portal/web/src/routes/router.jsx` | 전체 화면 경로 조립 |
| `apps/portal/web/src/components/layout` | 앱 공통 틀·레이아웃 |
| `apps/portal/web/src/components/common` | 여러 feature에서 쓰는 공통 UI |
| `apps/portal/web/src/components/ui` | shadcn/Radix 기반 기본 UI 요소 |
| `apps/portal/web/src/features/<feature>` | 업무 기능별 화면·컴포넌트·조회·상태·도우미 |
| `apps/portal/web/src/lib` | 앱 공통 맥락·프레임워크 연결·범용 도우미 |

## Feature 경계

다른 기능에서 사용할 수 있는 코드는 `index.js`에 공개합니다. 이를 facade라고 부릅니다.
기능 내부 파일을 직접 가져오면 파일 구조 변경이 다른 기능으로 퍼지므로 공개 진입점을 통합니다.
각 feature는 다음 하위 경로만 사용합니다.

| 하위 경로 | 역할 |
| --- | --- |
| `routes.jsx` | 기능에 속한 화면 경로 배열 |
| `index.js` | 다른 기능에서 사용할 공개 진입점 |
| `pages/` | URL에 직접 대응하는 화면 |
| `components/` | 해당 기능 안에서 쓰는 UI 요소 |
| `hooks/` | 해당 기능의 조회·상태·상호작용 hook |
| `api/` | API 호출 함수와 React Query 조회 키 |
| `store/` | 해당 기능 안에서 쓰는 UI 상태 |
| `utils/` | 외부 상태를 바꾸지 않는 기능 내부 도우미 |

기능 간 import는 `@/features/<feature>` 공개 진입점만 사용합니다. 허용된 의존 방향은
`auth -> account`, `emails -> account`, `line-dashboard -> account`입니다.
그 밖의 기능 조립은 `routes`, `components/layout`, `components/common`, `lib` 등 기능 바깥 계층에서 수행합니다.
`lib`에는 업무 전용 HTTP client·React Query hook·UI를 두지 않습니다. 위 경로는 모두 `apps/portal/web/src` 기준입니다.

## Route tree

전체 경로와 기능의 대응은 [화면 색인](../reference/02-inventory.md#프론트엔드-route)에서 확인합니다.
전역 연결은 `apps/portal/web/src/routes/router.jsx`, 개별 기능의 경로는 해당 `routes.jsx`가 담당합니다.

대표적으로 `/login`은 Auth, `/emails/**`는 Emails, `/observer`는 Observer가 담당합니다.
ESOP 대시보드는 `line-dashboard`, `/pm_spider`는 `pm-spider`에 대응하므로 URL과 폴더명이 항상 같지는 않습니다.
기능의 목적과 권한은 [기능 안내](../modules/README.md)를 확인합니다.

## API 호출 흐름

1. 화면이 해당 기능의 hook을 호출합니다.
2. Hook이 React Query로 조회 또는 변경 요청을 구성합니다.
3. API client가 `VITE_BACKEND_URL` 또는 상대 `/api/v1/**` 경로를 호출합니다.
4. 성공 응답은 React Query 캐시에 보관하고, UI 조작 상태만 store·컴포넌트에 저장합니다.
5. 변경 요청이 끝나면 관련 조회 범위만 무효화해 필요한 데이터를 다시 받습니다.

## 상태 관리 원칙

| 상태 유형 | 저장 위치 |
| --- | --- |
| 서버에서 온 목록/상세/권한 | React Query |
| 선택된 row, 필터 panel open 여부, tab, drawer 상태 | component state 또는 Zustand |
| 로그인 사용자 | auth provider/hook |
| route parameter | React Router |
| theme/layout shell 상태 | 공통 layout/lib |

서버 데이터를 Zustand에 복제하지 않습니다.

## UI와 레이아웃 원칙

- 앱 최상위 shell은 `h-screen flex flex-col`과 `flex-1 min-h-0 overflow-hidden`으로 화면 높이를 관리합니다.
- route 내부 page는 `h-full min-h-0`으로 부모 높이를 따릅니다.
- scroll 영역은 region마다 축별 하나만 둡니다.
- Tailwind semantic token을 먼저 사용하고 raw HEX/inline style은 피합니다.
- loading, empty, error, disabled, selected, focus 상태를 명시합니다.
- `apps/portal/web/src/components/ui/**`는 shadcn CLI 흐름 또는 명시 요청 없이 직접 수정하지 않습니다.

## 변경 시 갱신해야 하는 문서

- route 추가/변경: `docs/reference/02-inventory.md`, `docs/development/01-frontend.md`, 해당 `docs/modules/*.md`
- API client 변경: 해당 `docs/api/*.md`, 해당 `docs/modules/*.md`
- feature facade 변경: `docs/development/01-frontend.md`, 필요 시 boundary audit 결과
- feature 간 import 정책 변경: `apps/portal/web/AGENTS.md`, `docs/concepts/01-architecture.md`, boundary audit script
- 주요 화면 흐름 변경: 해당 `docs/modules/*.md`
