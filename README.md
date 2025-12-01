## Core Principles

### I. Vertical Slice Feature Isolation
모든 feature는 가능한 한 “작은 독립 제품”처럼 설계한다. apps/web/src/features/<feature>와 대응하는 Django app 단위로 페이지·컴포넌트·상태·API·타입을 자급자족하게 유지하고, import는 `src/components/ui/*`, `src/components/layout/*`, `src/components/common/*`, `src/lib/*`, 자기 자신의 `src/features/<feature>/*`로만 제한한다. 다른 feature의 query key, hook, 타입, 컴포넌트 사용은 금지하며 필요 시 중복 구현을 우선하고, 반복이 2회 이상이면 common 또는 lib로 승격한다. 목표는 feature 폴더를 통째로 복사해도 최소 수정으로 동작할 수준의 독립성이다.

### II. Radical Simplicity Over Abstraction
초보자도 이해할 수 있는 구조를 1순위로 두고, 복잡한 추상화·과도한 전역 상태를 피한다. “단순하지만 중복된 코드”를 “어렵고 복잡한 추상화”보다 우선한다. 헷갈릴 수 있는 부분에는 짧은 한글 주석을 남기고, 설계가 어려워지면 feature 경계를 다시 확인한다. 전역 공유가 필요해 보이면 우선 feature 내부에 가두고, 정말 반복되는 순간에만 common/lib로 승격한다.

### III. UI Stack & Theme Integrity
UI는 shadcn 기반 primitives(`src/components/ui`) → 레이아웃(`src/components/layout`) → 공통 조합형 UI(`src/components/common`) → feature별 컴포넌트 순서로 쌓는다. raw hex 색상은 금지하고 Tailwind 토큰 또는 CSS 변수만 사용하며, AppShell/Sidebar/Header/PageContainer 등 레이아웃은 도메인 의존성을 최소화하고 props로 주입한다. ThemeProvider는 light | dark | system을 지원하고, shadcn vendor 코드는 직접 수정하지 말고 토큰/변수로 override한다.

### IV. Routing as a Glue Layer
라우트는 오직 `src/routes`에서만 최종 정의되고, 각 feature는 `routes.tsx` 또는 `index.ts`로 자신이 제공하는 routes를 export한다. 라우트는 “어떤 path에 어떤 페이지” 정도만 알며 내부 비즈니스 로직, hooks, store를 직접 들여다보지 않는다. 중첩 깊이는 최대 2~3단으로 제한하고, loader/action은 URL 파라미터 검증·간단한 redirect·prefetch처럼 라우팅에 강하게 결합된 작업에만 쓴다. 모든 페이지는 AppShell 아래에서 렌더링한다.

### V. Data, State, and UX Discipline
서버 상태는 React Query가 책임지고, UI 상태는 useState/useReducer 등 지역 상태로 처리한다. Query key는 `["feature", "resource"]`, `["feature", "resource", { filters }]` 패턴을 따르며, invalidate는 관련 key만 정확히 지정하고 가능하면 feature 내부 api/ 모듈에서 캡슐화한다. loader 상태와 Query 캐시를 중복 관리하지 않으며, 로딩에는 skeleton/spinner를 feature가 책임지고 200+ row 리스트는 virtualization이나 pagination/infinite scroll을 고려한다. 전역 상태는 최후의 수단이다.

## Architecture & File System Contract

- Stack: React 19 + Vite + React Router + React Compiler + Tailwind + shadcn/ui (frontend) + Django + PostgreSQL (backend).  
- Frontend layout: `apps/web/src/components/ui`(primitives, 도메인 없음) / `components/layout`(AppShell/Sidebar/Header/PageContainer, 최소한의 도메인) / `components/common`(도메인 독립 조합형 UI).  
- Features: `apps/web/src/features/<feature>/` 안에 api/, components/, hooks/, pages/, store/, types/, utils/, routes.tsx, index.ts를 둔다. feature 외부에서 사용할 때는 루트 index/routes export만 import한다.  
- Routing glue: `apps/web/src/routes`가 각 feature routes를 합쳐서 정의하며, 다른 곳에서 라우트를 정의하지 않는다.  
- Theming: 색상/간격/타이포그라피 등은 Tailwind 토큰과 `src/styles/tokens.css`로 관리하고 raw hex는 금지한다.  
- Env: Vite 전역 환경 변수는 `VITE_` prefix 사용.  
- Backend: Django 앱을 feature와 1:1로 대응시키고 `/api/v1/<feature>` 네임스페이스를 따른다. 다른 app 모델 접근 시 serializer/service 레이어로 캡슐화하고 cross-app 쿼리는 최소화한다. DB는 UTC 저장, 프론트에서만 KST로 변환한다.

## Delivery Workflow & Quality Gates

- 단순성 유지: React + Tailwind + shadcn 조합으로 먼저 해결하고, 실제 문제 확인 전까지 과도한 최적화/추상화를 피한다.  
- UX & 접근성: AppShell 기반 일관 레이아웃, ARIA/키보드 내비게이션 준수, 반응형 고려. 로딩 skeleton/spinner와 pagination/virtualization을 feature 내부에서 책임진다.  
- Testing & validation: lint 통과가 필수(`npm run lint`). 자동 테스트가 부족한 경우 PR에서 수동 검증 단계를 기록한다. 중요한 흐름은 스냅샷/렌더링 테스트, 서버 상태 로직은 단위 테스트를 우선 고려한다.  
- Performance: 실제 성능 문제가 드러나기 전까지는 간결한 구현을 우선하고, 큰 데이터 화면에 대해서만 skeleton + pagination/infinite scroll/virtualization을 적용한다.  
- Migrations: 불필요하게 잘게 쪼개지 말고, 삭제 작업에는 롤백 전략을 포함한다. env 비밀은 `.env.local` 등에 두고 VCS에 커밋하지 않는다.

