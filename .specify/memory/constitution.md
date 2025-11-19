# 📜 Speckit Constitution — Full Integrated Version

*(React 19 + Vite + React Router + React Compiler + Tailwind + shadcn/ui + Django + PostgreSQL)*

---

## 🎯 Purpose

- React 19 + Vite + React Router + React Compiler + Tailwind + shadcn/ui 기반의 재사용 가능한 UI/Theme 프레임워크를 구축한다.
- 제품별 비즈니스 로직(대시보드, 내역, 설정, 인증 등)을 UI/Theme Core와 철저히 분리한다.
- 모든 규칙은 다음 계층 구조를 기준으로 해석한다:

```
UI primitives
Layout components
Common composite components
Feature modules
Backend apps aligned to features
```

- 전체 시스템은 “초보자도 이해할 수 있는 단순성”을 우선한다.

---

## 🌈 High-level Principles

- 초보자에게 직관적인 구조를 1순위로 둔다.
- 과도한 추상화, 복잡한 패턴, 불필요한 전역 상태 관리는 피한다.
- 재사용성보다 명확성 + 이해도를 우선한다.
- “단순하지만 중복된 코드”를 “어렵고 복잡한 추상화”보다 우선한다.
- 헷갈릴 수 있는 모든 부분에 짧은 한글 주석을 남긴다.

---

## 🧱 Architecture & Structure Principles

### 📁 File System Contract

#### `src/components/ui`

- shadcn 기반 UI primitives
- 도메인/비즈니스 로직 없음
- raw hex 색상 금지 (Tailwind tokens 또는 CSS 변수 사용)

#### `src/components/layout`

- AppShell / Sidebar / Header / PageContainer 위치
- 모든 페이지는 AppShell 아래에서 렌더링

#### `src/components/common`

- 여러 기능에서 공유되는 조합형 UI
- UI primitives의 조합으로만 구성

#### `src/features/<feature>`

- 특정 기능의 페이지·컴포넌트·hooks·API가 한 모듈에 모인다
- 명확한 entry(`index.tsx` 또는 `/pages`) 유지

#### `src/routes`

- React Router 라우팅 중앙 관리

#### `src/lib/theme`

- ThemeProvider, tokens, CSS variables

#### `src/lib/config`

- 앱 전역 환경 설정

#### `src/api`

- fetch/axios helper (선택)

---

## 🧭 Component Promotion Decision Tree

1. 처음에는 항상 feature 내부에서 시작한다.
2. 2개 이상의 feature에서 반복되면 → `components/common`
3. 도메인과 완전 독립적인 UI primitive면 → `components/ui`
4. 기준:
   - 도메인 의존 → feature
   - 중복 조합 UI → common
   - 순수 UI primitive → ui

---

## 🔌 React Router Contract

### 기본 원칙

- 라우트는 반드시 `src/routes`에서만 정의
- feature의 UI 로직은 라우트 파일로 절대 이동 금지
- 모든 페이지는 AppShell을 통한 일관된 레이아웃 사용

### Nested Routes

- URL 계층 구조가 자연스러울 때만
- 3단 이상 깊어지는 중첩 금지

### Loader / Action

- 데이터 로딩은 React Query가 기본
- loader/action은 딱 “라우팅과 강하게 결합된 작업”만
- loader 상태와 React Query 캐시를 중복 관리하지 않음

### Feature Entry

- `src/routes`는 feature의 페이지 컴포넌트만 import
- feature는 `pages/` 또는 `index.tsx`로 entry 제공

---

## 🔱 React Query Rules

### Query Key 구조

```
["feature", "resource"]
["feature", "resource", { filters }]
```

예시:

```
["dashboard", "summary", { lineId }]
["history", "list", { lineId, dateRange }]
```

### Shared Options

- `src/lib/query/defaultOptions.ts`에서 공통 옵션 관리
- 개별 컴포넌트에서 fetch 옵션 하드코딩 금지

### Invalidate 규칙

- mutation 이후에는 정확히 관련 key만 invalidate
- 광범위 `invalidateQueries` 금지

---

## 🎨 Theme & Styling

- ThemeProvider는 `light | dark | system` 모드 지원
- 모든 색상/간격/shadow 값은 Tailwind tokens 또는 CSS variables
- raw hex 사용 금지
- shadcn vendor 코드는 직접 수정하지 않는다 (테마 or CSS variables로 override)

---

## 🖥 Backend / Django / PostgreSQL Principles

### Django App Layout

```
app/
 ├ models/
 ├ serializers.py
 ├ views.py or api/
 ├ urls.py
 └ tests/
```

### Feature ↔ API Alignment

- `/api/v1/<resource>` ↔ `src/features/<resource>`
- 프론트/백 명명 규칙 일관하게 유지

### Migration

- 불필요하게 쪼개진 migration 금지
- 삭제 작업은 롤백 전략 포함
- 변경사항을 명확히 알 수 있는 commit/migration 메시지

### Timezone

- DB는 UTC
- 프론트에서만 KST 변환

---

## 🧠 State Management Principles

- 서버 상태 → React Query
- UI 상태 → `useState`/`useReducer`
- 전역 상태는 최후의 수단
- 서버 상태와 UI 상태 절대 혼합 금지

---

## ♿ UX & Accessibility

- AppShell 기반 공통 레이아웃
- shadcn ARIA/키보드 내비게이션 활용
- 반응형 디자인 고려
- 200+ row 리스트는 virtualization 고려

---

## ⚙️ Performance & DX

- 기존 스택 조합(React + Tailwind + shadcn)으로 해결 가능한지 먼저 검토
- 큰 데이터 화면은 skeleton + virtualization-friendly 구조 유지
- 과도한 최적화는 실제 문제 발생 시에만 적용
- 체크리스트: 다크모드 정상 / AppShell 유지 / raw hex 없음

---

## 🧪 Testing & Quality

### Frontend

- 중요 페이지/레이아웃: 스냅샷 + 렌더링 테스트
- UI 로직: 단위 테스트
- 실행: `npm test`

### Backend

- feature-level API 당 최소 1개의 contract test
- 인증/권한 케이스 포함
- 실행: `pytest` 또는 `python manage.py test`

### 철학

- 테스트가 복잡하면 코드 구조를 먼저 단순화
- 초보자 친화 우선

---

## 📝 PR Workflow & Enforcement

### 공통 체크리스트

- [ ] File System Contract 준수
- [ ] raw hex 색상 없음
- [ ] “왜 이렇게 했는지” 한글 주석
- [ ] 새 라이브러리: 필요성 설명 필수

### Frontend

- [ ] 라우트는 `src/routes`에서 정의
- [ ] AppShell 내부 렌더링
- [ ] React Query key 규칙 준수
- [ ] `defaultOptions` 사용
- [ ] lint / format / typecheck / test 통과

### Backend

- [ ] Django 앱이 도메인 기반
- [ ] `/api/v1` 네이밍 ↔ `features/*` 일치
- [ ] migration 깔끔
- [ ] lint / format / test 통과

---

## 🔧 Local Verification Commands

### Frontend

- Lint: `npm run lint`
- Format: `npm run format`
- Typecheck: `npm run typecheck`
- Test: `npm run test`

### Backend

- Lint: `ruff check .` 또는 `flake8`
- Format: `black .`
- Test: `pytest` 또는 `python manage.py test`

---

## 🔄 Change & Evolution

- 이 문서는 살아있는 헌법이다.
- 업데이트 시 항상 네 가지 우선순위를 따른다:
  1. 초보자 친화
  2. 간결함
  3. 예측 가능한 구조
  4. Theme/UI/State 일관성
