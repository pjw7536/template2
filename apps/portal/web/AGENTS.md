# Portal Web 개발 지침

## 적용 범위

이 지침은 `apps/portal/web/**`에 적용합니다. 상위 [Portal 지침](../AGENTS.md)도 함께 따릅니다.

## 작업별 스킬과 명명

아래 경로는 저장소 루트 기준입니다. 현재 작업에 해당하는 스킬만 읽습니다.

| 작업 | 스킬 |
| --- | --- |
| UI 구성 | `.codex/skills/product-ui-design-system/SKILL.md` |
| 레이아웃 구성 | `.codex/skills/compose-frontend-layout/SKILL.md` |
| UI 일관성 검사 | `.codex/skills/ui-consistency-audit/SKILL.md` |
| Feature 경계 검사 | `.codex/skills/frontend-boundary-audit/SKILL.md` |

`src`의 JSX 파일은 `.jsx`, 비 JSX 모듈은 `.js`를 사용합니다.
컴포넌트는 PascalCase, hook·util·store는 명시된 예외 외에는 camelCase를 사용합니다.

## Feature 구조

Feature는 `apps/portal/web/src/features/<feature>`에 두며 다음 하위 경로만 허용합니다.

| 경로 | 역할 |
| --- | --- |
| `pages/` | 경로에 대응하는 화면 |
| `components/` | Feature 내부 UI |
| `hooks/` | Query·상태·상호작용 hook |
| `api/` | API 호출과 query key |
| `store/` | Feature 내부 UI 상태 |
| `utils/` | 내부 도우미 |
| `routes.jsx` | Feature 라우팅 |
| `index.js` | 외부 공개 facade |

기본 최대 깊이는 2입니다. `components/`에서만 다음 조건을 모두 만족하면 한 단계 더 나눌 수 있습니다.

- 기존 컴포넌트 파일이 12개 이상이거나 사용자가 그룹 구성을 명시적으로 요청했습니다.
- 하위 폴더 이름은 `list`, `detail`, `form`, `dialog`, `table`, `chart`, `filters`, `cards`, `sections` 중 하나입니다.
- 그 아래에 추가 중첩 폴더를 만들지 않습니다.

다른 하위 폴더 이름이 필요하면 먼저 질문합니다.

## 공개 facade와 의존 방향

`apps/portal/web/src/features/<feature>/index.js`만 외부 공개 진입점입니다.
Named export만 사용하고 `export *`는 금지합니다.

Feature 간 의존은 `auth -> account`, `emails -> account`, `line-dashboard -> account`만 허용합니다.
허용된 의존도 반드시 `@/features/<feature>` facade로 사용합니다.

- `@/features/<otherFeature>/index.js`처럼 파일명을 직접 지정하지 않습니다.
- 다른 feature의 `components/*`, `pages/*`, `api/*` 등 내부 경로를 직접 import하지 않습니다.
- Feature 외부 조립 계층인 `routes/*`, `components/layout/*`, `components/common/*`, `lib/*`는 feature facade를 조합할 수 있습니다.
- `lib/*`에는 앱 shell context·프레임워크 어댑터·범용 도우미만 둡니다. 도메인 HTTP client·React Query hook·업무 UI를 두지 않습니다.

## Import 규칙

프로젝트 내부 절대 경로는 `@/`를 우선 사용합니다. `components/*` alias는 `components/...` 경로에서만 허용합니다.
한 파일에서 `@/components/...`와 `components/...`를 혼용하지 않고 기존 파일의 alias 방식을 유지합니다.

허용하는 절대 import 대상은 다음과 같습니다.

- `apps/portal/web/src/components/ui/*`
- `apps/portal/web/src/components/layout/*`
- `apps/portal/web/src/components/common/*`
- `apps/portal/web/src/lib/*`
- `apps/portal/web/src/features/<otherFeature>`의 facade: 위 의존 방향 또는 feature 외부 조립 규칙에 따릅니다.

## UI·라우팅·데이터

- 명시적으로 요청된 shadcn CLI 작업 외에는 `apps/portal/web/src/components/ui/**`를 직접 수정하지 않습니다.
- 모든 feature는 `routes.jsx`를 공개합니다. 전역 라우팅은 `apps/portal/web/src/routes/*`에서만 조립합니다.
- Route는 `components/layout/*`를 조합할 수 있지만 route 파일 안에 레이아웃 컴포넌트를 정의하지 않습니다.
- Route에 업무 로직·데이터 처리·파생 UI 로직을 넣지 않습니다.
- 서버 데이터의 기준은 React Query입니다. 배열 query key를 사용하고 중복 key를 피하며 최소 범위만 invalidate합니다.
- 서버 데이터를 Zustand에 복제하지 않습니다. Zustand는 feature 내부 UI·상호작용 흐름 상태에만 사용합니다.

## 스타일·React·레이아웃

- Tailwind만 사용하고 디자인 토큰과 `dark:`를 적용합니다.
- 새 UI 기본 요소를 만들기 전에 `apps/portal/web/src/components/ui/*`의 shadcn/Radix 요소를 먼저 사용합니다.
- 제품 UI 판단은 `product-ui-design-system` 스킬을 따릅니다.
- `bg-card`, `text-muted-foreground`, `border-border`, `text-destructive`, `bg-primary` 등 의미 기반 토큰을 우선 사용합니다.
- 꼭 필요한 경우 외에는 임의 HEX와 inline style을 금지합니다. 라이브러리 연결에 필요한 CSS 변수 기반 동적 크기·색상은 허용합니다.
- `useMemo`, `useCallback`, `React.memo`는 필요한 경우에만 사용합니다.
- 해당 화면의 loading·empty·error·disabled·selected·hover/focus·dark mode 상태를 명시합니다.
- 조작 요소에는 접근 가능한 레이블, 키보드 접근, 눈에 보이는 focus 상태를 제공합니다.

레이아웃의 높이와 스크롤은 다음 규칙을 따릅니다.

| 영역 | 규칙 |
| --- | --- |
| 각 화면 영역 | 축별 스크롤 컨테이너 하나 |
| 스크롤 요소 | `min-h-0` 필수 |
| 앱 최상위 shell | `h-screen flex flex-col` + 고정 header + `flex-1 min-h-0 overflow-hidden` |
| Route 내부 page | `h-full min-h-0`으로 부모 높이를 따르고 `h-screen`을 중복 사용하지 않음 |

세부 패턴은 `compose-frontend-layout` 스킬을 따릅니다.

## 검증

| 변경 영역 | 실행하거나 권고할 검사 |
| --- | --- |
| Frontend UI | `make audit-ui` |
| Feature import·export·라우팅 | `make audit-web-boundary` |
| 광범위한 frontend 변경 | `make audit` |

감사 결과는 검토 후보입니다. 요청 범위 밖의 기존 문제까지 수정하지 않습니다.
