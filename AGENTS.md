🧭 agents.md — Project Constitution for Developers & LLM Agents  
(React 19 + Vite + JS + Tailwind + shadcn/ui + Django + PostgreSQL)

이 문서는 사람 개발자와 LLM 에이전트 모두가 반드시 따라야 하는 행동 규약입니다.  
모든 코드는 스펙 기반 개발(SDD)을 기준으로 하며, 아키텍처·폴더·UI/테마·라우팅·상태 규칙을 어기는 코드는 즉시 수정 대상입니다.

## 1. Core Architectural Principles
### 1-1. Vertical Slice Isolation
- 모든 비즈니스 기능(feature)은 완전히 독립적이어야 한다.
- feature 경로: `apps/web/src/features/<feature>`
- feature 내부 구성 디렉터리 예시:
  - `pages/`
  - `components/`
  - `api/`
  - `hooks/`
  - `store/`
  - `utils/`
  - `routes.jsx`
  - `index.js`
- feature 외부에서 import 가능한 대상:
  - `apps/web/src/components/ui/*`
  - `apps/web/src/components/layout/*`
  - `apps/web/src/components/common/*`
  - `apps/web/src/lib/*`
  - 다른 feature의 공식적으로 export된 인터페이스
- 중복 구현 원칙:
  - 처음에는 각 feature 내부에서 중복 구현을 허용한다.
  - 같은 패턴이 2회 이상 반복될 때만 `components/common` 또는 `lib`로 승격한다.
  - 승격 시에도 feature 간 결합도를 올리지 않도록 주의한다.

### 1-2. Radical Simplicity
- 복잡한 추상화 금지: “슈퍼 베이스 훅”, “모든 걸 처리하는 서비스” 같은 거대 추상화 금지
- 전역 상태는 진짜 필요할 때만 사용: 먼저 컴포넌트 내부 상태 → feature 내부 context → 그 다음에야 전역 상태를 고려
- 주석 원칙: “무엇을 하는지” 설명 대신, “왜 이렇게 했는지”를 짧고 명확하게 남긴다.

### 1-3. UI Stack & Theme Integrity
- UI 계층 구조:
  - Primitives (shadcn/ui)
  - Layout components (`components/layout`)
  - Common composite components (`components/common`)
  - Feature UI (`features/<feature>/components`)

🔒 UI Components Immutability Rule (수정 금지 규칙)
- `apps/web/src/components/ui/**/*` 는 절대 수정 금지인 vendor 계층이다.
- `ui/`는 shadcn/ui 프리미티브를 그대로 보존하는 레이어다.
- `layout/`, `common/`은 `ui`를 조합한 공유 레이어이며, 필요 시 수정 가능하지만 base `ui`는 건드리지 않는다.
- `ui` 컴포넌트에 대해서:
  - 직접 수정하지 않는다.
  - 내부 구현을 커스터마이징하지 않는다.
  - 허용되는 것: className override, props 조합, wrapper 컴포넌트에서 재사용.
- UI 변경이 필요할 때:
  - 해당 feature 내부에서 wrapper/조합 컴포넌트로 새로운 UI를 만든다.
  - base `ui` 컴포넌트를 절대 뜯어고치지 않는다.
- 새로운 프리미티브가 필요하면:
  - shadcn CLI로 `apps/web/src/components/ui`에 추가한다.
  - 직접 `ui` 폴더에 새 파일을 만들지 않는다.
- 요약:
  - `apps/web/src/components/ui` = vendor-like immutable layer(불변 계층)
  - 사람/LLM 모두 이 계층은 수정 대상이 아니다.
  - 진화가 필요한 부분은 `layout` / `common` / 각 feature 내부에서 처리한다.

- 테마 규칙
  - Hex 색상 직접 사용 금지
  - Tailwind preset + CSS 변수(예: `bg-primary`, `text-muted-foreground`)만 사용.
  - 다크 모드:
    - ThemeProvider는 `light | dark | system` 값을 유지한다.
    - 다크 모드 전용 스타일이 필요하면 Tailwind의 `dark:` 프리픽스를 사용한다.

### 1-4. Routing as Glue
- 모든 라우팅은 `apps/web/src/routes`에서 정의한다.
- 각 feature는 route entry만 export한다 (예: `getRoutes()` 혹은 route config 객체).
- 라우트 파일에서 비즈니스 로직 훅/서비스를 직접 import 하지 않는다: 역할은 params 검증, redirect, 데이터 prefetch 정도로만 한정한다.
- 중첩 라우팅 깊이: 2–3단계 이내 유지.
- 모든 페이지는 공통 AppShell 아래에 위치한다.

### 1-5. Data / State / UX
- 서버 상태 관리: React Query 사용 (또는 이에 준하는 서버 상태 라이브러리).
- query key 형식: `['feature', 'resource', filters]`.
- 캐시 무효화: 가능한 한 정확한 key만 invalidation 한다(예: `invalidateQueries(['feature','list'])` 등).
- loader 데이터 vs query 캐시: 같은 데이터를 두 번 관리하지 않는다. (하나는 loader, 하나는 query로 나누지 말 것)
- 대용량 UI(200+ rows): pagination, virtualization, infinite scroll, skeleton 중 최소 한 가지는 필수 적용.

## 2. Architecture & File System Contract
### 2-1. Tech Stack
- Frontend:
  - React 19
  - Vite
  - JavaScript (ES2022, `.js` / `.jsx`)
  - Tailwind CSS + shadcn/ui
- Backend:
  - Django
  - PostgreSQL
  - 서비스/serializer 기반 구조 유지

### 2-2. Frontend Boundaries
- 공용 레이어:
  - `apps/web/src/components/ui`
  - `apps/web/src/components/layout`
  - `apps/web/src/components/common`
  - `apps/web/src/lib`
  - `apps/web/src/styles`
  - `apps/web/src/hooks`
  - `public/`
- 🎯 중요:
  - `apps/web/src/components/ui`는 수정 금지된 vendor-like 계층
  - `layout` / `common`은 `ui`를 조합한 공유 레이어로, 필요 시 리팩터링 및 확장 가능
- feature 레이어:
  - `apps/web/src/features/<feature>/...`
  - 비즈니스 로직, 해당 도메인의 UI, 훅, 스토어는 최대한 feature 내부에 가둔다.

### 2-3. Backend Boundaries
- API prefix 규칙: `/api/v1/<feature>` 형태로 유지.
- cross-app 모델 접근 금지: 다른 Django app의 모델에 직접 의존하지 말고, 서비스/도메인 레이어를 통해 접근.
- 시간 관련 데이터: DB에는 항상 UTC 기준으로 저장하고, 프론트에서 렌더링 시 타임존 변환.

## 3. Project Structure (Frontend)
- 엔트리 포인트: `apps/web/src/main.jsx`
- 최상위 AppShell: `apps/web/src/App.jsx`
- 공용 UI:
  - `apps/web/src/components/ui/*`
  - `apps/web/src/components/layout/*`
  - `apps/web/src/components/common/*`
- 라우트: `apps/web/src/routes/*`

## 4. Build / Dev / Test Commands
- Frontend
  - 의존성 설치: `npm install`
  - 개발 서버 실행: `npm run dev`
  - 프로덕션 빌드: `npm run build`
  - 빌드 결과 프리뷰: `npm run preview`
- Backend
  - 마이그레이션: `python manage.py migrate`
  - 개발 서버 실행: `python manage.py runserver`

## 5. Coding Style & Naming (JavaScript)
### 5-1. 일반 규칙
- 파일명:
  - 컴포넌트: `PascalCase.jsx` (예: `ThemeToggle.jsx`)
  - 일반 JS 모듈/유틸/훅: `camelCase.js` (예: `useTheme.js`, `formatDate.js`)
- 코드 스타일: 모던 ES 모듈 사용(`import` / `export`), 함수형 React 컴포넌트만 사용(클래스 컴포넌트 금지).
- 스타일링: Tailwind 유틸리티 클래스 + CSS 변수 조합.
- 조건부 클래스: `clsx` 또는 같은 역할의 헬퍼 유틸 사용(직접 문자열 이어붙이기 지양).
- 인라인 스타일은 꼭 필요할 때만 사용.

### 5-2. 타입 관련 규칙 (JS 기준)
- 프로젝트는 순수 JavaScript 기반을 기본으로 한다.
- 타입 정보가 필요하면:
  - JSDoc을 활용해 함수 인자/리턴 타입과 객체 shape를 설명한다.
- TypeScript 파일(`.ts`/`.tsx`)은 기본적으로 사용하지 않는다.
- 예외적으로, 별도 논의 후 도입하는 경우에도 JS 코드 베이스에 부담을 주지 않는 선에서만 제한적으로 사용한다.
- 목표: “초보자도 바로 읽고 이해할 수 있는 JavaScript”를 최우선으로 한다.

## 6. Testing
- 기본 도구: Vitest, React Testing Library(RTL)
- 테스트 파일명:
  - 컴포넌트 테스트: `Component.test.jsx`
  - 유틸/함수 테스트: `something.test.js`
- 테스트 원칙:
  - DOM 구조에 과도하게 의존하지 말고, 사용자 관점(텍스트, 역할, 라벨)으로 검사한다.
  - 주요 시나리오(렌더링, 상호작용, 에러 처리)는 최소 1개 이상의 테스트를 갖도록 한다.
