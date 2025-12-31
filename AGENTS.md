# 🧭 agents.md — Ultra‑Optimized Constitution for LLM Agents (Improved v2)

### (Strict, Unambiguous, Machine‑Executable Rules)

This document defines **non‑negotiable rules** that all LLM agents MUST obey.
Every rule eliminates ambiguity, enforces determinism, and guarantees a consistent system architecture.

When uncertain, an LLM agent MUST **ask for clarification** before generating code.

---

# 1. Global Execution Rules

## 1‑1. Deterministic Behavior

LLM agents MUST:

- Follow every rule exactly.
- Produce deterministic folder paths, naming, and architecture.
- Never invent new patterns unless explicitly ordered.
- Prefer explicitness over cleverness.
- Ask whenever **any** detail is unspecified **unless** it is classified as a Soft Assumption (see §1‑3‑2).

## 1‑2. Output Format Rules

- All code MUST be syntactically valid.
- All file paths MUST use forward slashes.
- All imports MUST resolve to real files.
- Components MUST use PascalCase.
- Hooks MUST use camelCase.
- Feature exports MUST be routed through each feature’s `index.js`.
- In `apps/web/src`, files that render JSX MUST use `.jsx` (non‑JSX modules MUST use `.js`).

## 1‑3. User Request Understanding Gate (Mandatory)

### 1‑3‑1. Before any implementation

Before ANY implementation work (writing/editing files, running commands/tools, proposing file/folder locations), the LLM MUST:

1. Summarize the user request in TWO versions:
   - `Summary (EN): ...`
   - `요약 (KR): ...`
2. List all ambiguities / decisions as questions.
3. Classify questions into:
   - **Hard‑Block Questions (must be answered to proceed)**
   - **Soft Questions (safe defaults allowed; proceed with assumptions)**

If there are **Hard‑Block Questions**, the LLM MUST:

- Ask the user to confirm/correct the summaries and answer the Hard‑Block Questions.
- STOP and wait for answers.

If there are **no Hard‑Block Questions**, the LLM MUST:

- Proceed immediately.
- Clearly state any Soft Assumptions being used.

### 1‑3‑2. Soft Assumption Defaults (Allowed)

The LLM MAY proceed without asking when ONLY these are unclear:

- Copy text/labels/placeholder wording
- Spacing, minor UI layout details, icon choice
- Default sorting when not specified
- Empty/loading state UX (sensible minimal patterns)

Soft Assumptions MUST be:

- Explicitly listed before implementation
- Easy to change later

### 1‑3‑3. Hard‑Block Criteria (Always Ask)

These MUST be Hard‑Block Questions:

- API schema/contract, request/response shape, pagination rules
- Database schema/migrations, unique constraints, indexes
- Auth/permissions and role rules
- Business rules that affect correctness (billing, coupon rules, scheduling rules, etc.)
- Cross‑feature dependency direction when ambiguous

## 1‑4. Comment Language Rules (Mandatory)

LLM agents MUST:

- Write all comments and docstrings in Korean (한글).
- Proper nouns MUST remain in their original form; do not translate them into Korean.
- When editing a file, translate any existing English comments/docstrings in that file to Korean.
- If English is strictly required by a tool or specification, include Korean alongside the required English (Korean‑first).

---

# 2. Architectural Rules (LLM‑Strict)

## 2‑0. Modular Monolith (Single Deployment)

This codebase is a modular monolith: one deployable unit with strict domain/feature separation.

### LLM MUST obey:

- Keep a single deployment artifact and runtime boundary (no microservices) unless explicitly instructed.
- Enforce feature boundaries using the vertical slice rules below.
- Cross‑feature access must go through public facades only (frontend `features/<feature>/index.js`, backend `api.<feature>.services` or `selectors.py`).
- Shared code must live only in approved shared locations; do not move domain logic into shared modules.

## 2‑1. Vertical Slice Isolation (Frontend)

Each feature MUST be a fully isolated vertical slice.

### Feature Path

```
apps/web/src/features/<feature>
```

### Allowed Subfolders

```
pages/
components/
hooks/
api/
store/
utils/
routes.jsx
index.js
```

### Folder Depth Rule

- Default: NO nesting deeper than 2 levels.
- Optional exception: one extra level under `components/` is allowed only when:
  - the feature already contains 12+ component files, OR the user explicitly requests grouping
  - the subfolder name is one of: `list`, `detail`, `form`, `dialog`, `table`, `chart`, `filters`, `cards`, `sections`
  - no further nesting is allowed
- If a different subfolder name is needed, ask (Hard‑Block).

### LLM MUST obey:

- NO new folders unless explicitly allowed above.
- NO cross‑feature imports (except from another feature’s public facade).

## 2‑2. Public Facade Contract (Frontend)

Each feature’s `index.js` is the **only** public surface.

`index.js` MAY export:

- `routes` (from `routes.jsx`)
- route‑level pages (Page components used by `routes.jsx`)
- public hooks
- public API helpers
- public, reusable feature components intended for external use

`index.js` MUST NOT export:

- internal/private components used only inside the feature
- internal‑only pages (non‑route or helper pages)

`index.js` SHOULD:

- keep exports explicit and minimal (use named exports only)

### 2‑2‑1. Facade Export Rules (Frontend)

LLM MUST obey:

- `apps/web/src/features/*/index.js` MUST NOT use `export *`.
- `index.js` MUST export only modules intended for cross‑feature use (documented or explicitly requested).
- If the intended public surface is unclear, ask (Hard‑Block).

---

# 3. Frontend Import Rules (Strict)

## 3‑1. Allowed Imports (project‑internal absolute imports only)

This rule applies to **project‑internal absolute imports**. It does NOT restrict:

- npm package imports (e.g. `react`, `react-router-dom`, `@tanstack/react-query`)
- relative imports inside the same feature (e.g. `./components/Foo.jsx`, `../utils/dateUtils.js`)

Project‑internal absolute imports MUST resolve under:

- `apps/web/src/components/ui/*` (e.g. `@/components/ui/*`, `components/ui/*`)
- `apps/web/src/components/layout/*` (e.g. `@/components/layout/*`, `components/layout/*`)
- `apps/web/src/components/common/*` (e.g. `@/components/common/*`, `components/common/*`)
- `apps/web/src/lib/*` (e.g. `@/lib/*`)
- `apps/web/src/features/<otherFeature>` (facade only)

## 3‑2. Import Style Rules (Repo‑Specific)

- Prefer `@/` for project‑internal absolute imports.
- The `components/*` alias is allowed **only** for `components/...` paths.
- Do not mix `@/components/...` and `components/...` within the same file.
- When editing an existing file, keep its current alias style to avoid churn.
- Outside `components/layout` and `components/common`, import via their `index.js` (e.g. `@/components/layout`, `@/components/common`).

## 3‑3. Cross‑Feature Import Format (Single Standard)

Cross‑feature imports MUST use exactly this form:

```js
import { something } from "@/features/<otherFeature>"
```

- The bundler MUST resolve this to `features/<otherFeature>/index.js`.
- Importing `@/features/<otherFeature>/index.js` explicitly is NOT allowed.

### Forbidden examples

- `@/features/<otherFeature>/components/*`
- `@/features/<otherFeature>/pages/*`
- `@/features/<otherFeature>/api/*`

Anything else is **INVALID**.

---

# 4. UI Stack Rules

## 4‑1. Immutable UI Layer

LLM agents MUST NOT manually edit:

```
apps/web/src/components/ui/**
```

UI primitives may only be added/updated via the shadcn CLI (and only when explicitly requested).

## 4‑2. UI Assembly Hierarchy

LLM MUST assemble UI in the following order:

1. UI primitives (`components/ui/*`)
2. Layout components (`components/layout/*`)
3. Common shared components (`components/common/*`)
4. Feature‑specific UI (`features/<feature>/components/*`)

Hierarchy inversion is forbidden.

---

# 5. Routing Rules

## 5‑1. Feature Route Export

Every feature MUST expose a `routes.jsx`.

## 5‑2. Global Routes

Global routing ONLY exists under:

```
apps/web/src/routes/*
```

Routes MAY compose layout components from `apps/web/src/components/layout/*`, but MUST NOT define layout components under `apps/web/src/routes/*`.

## 5‑3. No Business Logic in Routes

Routes MAY:

- Declare structure
- Provide element
- Validate params
- Redirect

Routes MUST NOT contain:

- Business logic
- Data logic
- Derived UI logic

---

# 6. State & Data Rules

## 6‑1. React Query Rules

React Query is the ONLY source of truth for server data.

LLM MUST:

- Use array‑based query keys.
- Avoid redundant keys.
- Invalidate the smallest necessary scope.
- NEVER mirror server data into Zustand.

## 6‑2. Zustand Rules

Zustand is ONLY allowed for:

- UI state
- Interaction flows
- Multi‑step forms
- Temporary shared state (within the same feature)

Forbidden:

- Server data of any kind
- Redux‑like mega‑stores
- Global cross‑feature state

Store Path Rule:

```
apps/web/src/features/<feature>/store/useSomethingStore.js
```

---

# 7. Coding Rules

## 7‑1. Naming

- Components → PascalCase
- Hooks → camelCase
- Utilities → camelCase
- Zustand stores → useSomethingStore
- Pages → PascalCase
- API modules → camelCase

## 7‑2. Styling

LLM MUST:

- Use Tailwind classes only
- Use design tokens (`text-primary`, `bg-muted`, etc.)
- Use `dark:` prefix for dark mode

LLM MUST NOT:

- Use arbitrary HEX values
- Use inline styles unless strictly necessary

---

# 8. React 19 Rules

LLM MUST avoid premature optimization.

Forbidden unless required:

- useMemo
- useCallback
- React.memo

Allowed only when:

- Heavy computation exists
- Library requires identity stability

---

# 9. Backend / Django Rules (LLM‑Strict)

## 9‑1. Domain App (Feature) Isolation

Backend MUST be organized by business‑domain Django apps (“features”).

### Domain App Path

```
apps/api/api/<feature>
```

Each `<feature>` is a real Django app installed as `api.<feature>`.

### Allowed Files / Folders (max depth 2)

```
apps.py
models.py
urls.py
callback_urls.py   (auth only; OIDC form_post callback)
views.py
serializers.py
services/   (required; includes `services/__init__.py` facade)
selectors.py
permissions.py
admin.py
tests.py
migrations/
management/commands/   (optional)
```

Infrastructure / shared packages are allowed only at:

```
apps/api/api/common
apps/api/api/auth
apps/api/api/rag
apps/api/api/management
```

LLM MUST obey:

- NO new backend folders outside the paths above.
- NO nesting deeper than 2 levels (except `migrations/` and `management/commands/`).
- NO cross‑feature imports except through another feature’s public `services/__init__.py` (facade) or `selectors.py`.
- Every concrete DB model MUST live in exactly one `<feature>/models.py`. Creating new models in `apps/api/api/models.py` is **FORBIDDEN**.
- Shared base classes/mixins MAY live in `apps/api/api/common/models.py` and MUST be `abstract = True`.
- When touching legacy root models, LLM MUST migrate them into the correct feature app (with a new migration) instead of extending the root file.
- Extra URL modules are allowed only when strictly necessary; name them `<purpose>_urls.py` and include them from the feature `urls.py` (exception: `api.auth.callback_urls` is included directly at `/auth/`).

## 9‑2. Service/Selector Architecture

### Responsibility

- `views.py` → HTTP only: auth/permissions, param parsing, serializer validation, calling services/selectors, returning responses.
- `serializers.py` → input/output schema + validation only.
- `permissions.py` → DRF permission classes only.
- `services/__init__.py` (facade) and `services/*` → ALL business logic and write operations (create/update/delete), transactions, external API calls.
- `selectors.py` → read‑only ORM queries (filtering, ordering, annotation). NO side effects.
- `models.py` → schema + pure domain rules. NO queries or business workflows.
- Views/services MUST NOT run read ORM queries directly; they MUST call selectors instead.

### Allowed Imports (one‑way)

This rule applies to **project‑internal imports**. Python stdlib, Django (`django.*`), and DRF (`rest_framework.*`) imports are always allowed.

- `views.py` may import: `serializers`, `permissions`, `services`, `selectors`, `api.common.*`
- `services/__init__.py` may import: `services/*`
- `services/*` may import: `selectors`, `models`, `api.common.*`, `api.<otherFeature>.services`
- `selectors.py` may import: `models`, `api.common.*`, `api.<otherFeature>.selectors`
- `models.py` may import: Django/stdlib only, plus `api.common.*` for shared types/constants

Anything else is **INVALID**.

## 9‑3. Routing & API Shape

LLM MUST:

- Use versioned prefixes: `/api/v1/<route-scope>/...` for API endpoints.
- Exception: OIDC callbacks under `/auth/` (non‑versioned) are allowed only in `api.auth.callback_urls`.
- Keep feature routes inside `apps/api/api/<feature>/urls.py`.
- Keep global routing ONLY in `apps/api/api/urls.py` using `include()`; global `urls.py` must NOT import feature views directly.
- `apps/api/api/urls.py` MUST be a registry only, e.g.:
  - `path("api/v1/emails/", include("api.emails.urls"))`
  - `path("api/v1/appstore/", include("api.appstore.urls"))`
- Feature `urls.py` MUST define relative paths (no leading `/api/v1/<feature>` inside a feature).
- Route scope SHOULD match the feature domain slug; legacy mismatches (e.g. `api.drone` → `/api/v1/line-dashboard/`) are allowed but must not be expanded without explicit instruction.
- Ensure routes contain no business logic (delegate to services/selectors).
- Name endpoints with nouns, collections plural: `emails/`, `appstore/apps/`.

## 9‑4. Database & Model Naming

LLM MUST:

- Use snake_case for fields/columns: `created_at`, `user_sdwt_prod`.
- Use singular PascalCase for model classes: `Email`, `AppStoreComment`.
- Use per‑domain table prefixes:
  - `db_table = "<feature>_<entity>"`
- Set `db_table` on every model.
- Primary key is `id` (BigAutoField). UUID only when an external identifier is required.
- Timestamps are UTC, timezone‑aware:
  - required: `created_at`
  - optional: `updated_at`, `deleted_at`
- Index / constraint naming:
  - `idx_<table>_<cols>`
  - `uniq_<table>_<cols>`

## 9‑5. Transactions & Side Effects

LLM MUST:

- Wrap multi‑step writes in `transaction.atomic()`.
- Keep external calls (RAG, email servers, etc.) inside `services/__init__.py` (facade) or `services/*`.
- Never perform writes inside `selectors.py` or `models.py`.

## 9‑6. Readability / Beginner Rules

LLM MUST:

- Prefer explicit, linear code over clever abstractions.
- Avoid metaprogramming, dynamic imports, or hidden magic.
- Keep functions/classes small and single‑purpose (≈30–50 lines max).
- Use descriptive names; avoid non‑standard abbreviations.
- Add type hints to public services and selectors.
- Put docstrings on every public service/selector explaining inputs/outputs and side effects.

## 9‑7. Testing & Migrations

LLM MUST:

- Add or update tests when changing business logic.
- Prefer unit tests for `services/__init__.py` (facade) and `selectors.py`; keep view tests minimal (happy + main error cases).
- Never edit an already‑applied migration; always create a new one.

## 9‑7‑1. 테스트/커맨드 경계 규칙 (추가)

LLM MUST:

- 테스트 코드에서 다른 도메인의 `models` 직접 import 금지 (예외: `migrations/`).
- 테스트 코드에서 다른 도메인의 내부 모듈(`api.<feature>.services.*` 등) 직접 import 금지; 반드시 `services/__init__.py` 파사드를 사용.
- 도메인 전용 관리 커맨드는 해당 도메인 앱 경로(`apps/api/api/<feature>/management/commands/`)에만 위치.
- 공용 관리 커맨드(`apps/api/api/management/commands/`)는 다른 도메인의 `models`/ORM 직접 접근 금지, `services`/`selectors` 파사드만 사용.

## 9‑8. New Feature Checklist (Beginner‑Friendly)

When adding a new backend feature, LLM MUST follow this exact flow:

1. Create `apps/api/api/<feature>/` as a Django app with `__init__.py` and `apps.py` (`name = "api.<feature>"`).
2. Register the app in `apps/api/config/settings.py` → `INSTALLED_APPS`.
3. Add `models.py` with `db_table = "<feature>_<entity>"` prefixes, then create a new migration.
4. Add `serializers.py` for all request/response shapes.
5. Add `selectors.py` for all read queries.
6. Add `services/__init__.py` (facade) for all business logic and writes (implementations in `services/*`).
7. Add `views.py` that only wires HTTP → serializers → services/selectors.
8. Add `urls.py` with relative routes, then include it in `apps/api/api/urls.py` under `/api/v1/<feature>/`.
9. Add `tests.py` focusing on services/selectors first.

Skipping or re‑ordering these steps is INVALID.

## 9‑9. Commenting & Documentation Rules (Mandatory)

Readability is first‑class. Backend code MUST be step‑by‑step explainable with detailed comments.
All required comments/docstrings MUST be Korean (한글) per §1‑4.

### 9‑9‑1. When Detailed Comments Are REQUIRED

- The user asks for: "전체 코드", "다시 줘", "주석 달아줘", "설명 포함", or similar.
- The file contains request parsing, validation, permission checks, or multiple branches.
- The logic has non‑trivial rules (upsert, dedupe, timezone conversion, pagination).
- Any function/class is >= 25 lines OR has 2+ conditional branches.

### 9‑9‑2. Required Comment Structure (Python)

1. Module header comment:

   - purpose
   - main endpoints/classes
   - key invariants/assumptions
2. For every public function/service/selector/view method:

   - docstring: what/inputs/returns/side‑effects/errors
3. For long/complex functions:

   - step markers: `# 1) 요청 파싱` ...
   - explain why for non‑obvious decisions
4. Inline comments:

   - explain intent, not restate code

### 9‑9‑3. Comment Density

- Target: one meaningful comment per logical block (≈5–15 lines).
- Too sparse is INVALID.
- Too verbose is INVALID if it drowns the code.

### 9‑9‑4. Request/Response Examples (Views)

For any APIView/endpoint:

- MUST include at least one example request payload / query params in the docstring.
- MUST document snake_case + camelCase compatibility if supported.

### 9‑9‑5. Forbidden Comment Patterns

- Comments that contradict the code
- Comments that mention internal tool output or assistant meta commentary
- Comments that explain history instead of current behavior

### 9‑9‑6. Standard Template (Python)

For complex functions/methods:

- `# -----------------------------------------------------------------------------`
- `# 1) <단계 제목>`
- `# -----------------------------------------------------------------------------`

Repeat per step.

Additionally:

- Constants MUST be grouped and labeled (timezone/constants/pagination/etc.).
- Major sections of a file SHOULD be separated with "# =============================================================================".

---

# 10. File Generation Rules

When generating files, LLM MUST:

1. Output full folder path
2. Output complete file content
3. Ensure imports resolve
4. Comply with architecture
5. Follow naming rules

When updating files:

- Preserve existing structure
- Preserve exports
- Never refactor beyond the requested scope

---

# 11. Error Handling Rules

The LLM MUST ask for clarification (Hard‑Block) when:

- A folder name is ambiguous
- File location is unclear
- API schemas are missing
- More than one valid interpretation exists

LLM MUST NOT guess.

---

# 12. Layout Rules (Strict for All Features)

## 12‑1. Layout Philosophy

Layout follows two universal principles:

1. Outer containers define structure and fixed height.
2. Avoid nested scroll regions on the same axis **within the same region**.

A "region" is a single scroll context (page main, a pane, or an overlay body).
If multiple scroll regions are nested on the same axis in the same region → INVALID.

### Overlay Exception (Modal/Popover)

- Scroll inside overlays (modal/popover/drawer) is allowed.
- Overlay scroll is considered a separate region from page scroll.

## 12‑2. Global Page Skeleton Rule

Every page MUST follow this layout skeleton:

```jsx
<div className="h-screen flex flex-col">
  <header className="h-16 shrink-0">...</header>

  <main className="flex-1 min-h-0 overflow-hidden">
    {children}
  </main>
</div>
```

LLM MUST:

- Use `h-screen flex flex-col`
- Keep header fixed height with `shrink-0`
- Wrap content in `flex-1 min-h-0 overflow-hidden`
- Ensure scrolling happens inside main, not outside

## 12‑3. Flex vs Grid Rules

### Flex MUST be used for:

- One-direction layout (row/col)
- Toolbars, buttons, headers
- Alignment and distribution

### Grid MUST be used for:

- Multi-region layouts (list + detail)
- Top-fixed + bottom-scroll structures
- Mixed row/column ratio layouts

## 12‑4. Scroll Rules

### Rule A — Only ONE scroll container per axis, per region

```jsx
<div className="min-h-0 overflow-y-auto">...</div>
```

Sibling panes may each be scrollable.

### Rule B — Scrollable elements MUST have `min-h-0`

### Rule C — Official top-fixed/bottom-scroll pattern

```jsx
<div className="grid h-full min-h-0 grid-rows-[auto,1fr]">
  <div>Fixed Area</div>
  <div className="min-h-0 overflow-y-auto">Scrollable Area</div>
</div>
```

## 12‑5. Two‑Pane Layout Rule

(Left list + Right detail)

```jsx
<div className="grid flex-1 min-h-0 gap-4 md:grid-cols-2">
  <div className="grid min-h-0 grid-rows-[auto,1fr] gap-2">
    <div className="h-auto overflow-hidden">{filters}</div>
    <div className="min-h-0 overflow-y-auto">{list}</div>
  </div>

  <div className="min-h-0 overflow-y-auto">{detail}</div>
</div>
```

## 12‑6. Padding Responsibility Rules

### Layout components control:

- Page-level padding (use layout defaults like `p-4 md:p-6` or `px-4 pb-3`)
- Section spacing (`gap-*`)
- Outer structure
- Work-area padding

### Components control:

- Internal padding (`p-4`, `p-3`, etc.)
- Internal spacing (`gap-2`, `gap-3`)

STRICT RULES:

- Parent MUST NOT adjust child internal padding
- Child MUST NOT define page-level padding
- Avoid duplicated padding across layers
- Keep existing layout-provided padding unless explicitly requested to change it

## 12‑7. Spacing Rules

- Page padding: `p-4 md:p-6` (ContentLayout default) OR `px-4 pb-3` (AppLayout default)
- Section gaps: `gap-4`
- Internal content spacing: `gap-2` or `gap-3`
- Large segmentation: `gap-6`

Arbitrary spacing values are forbidden.

## 12‑8. Layout Componentization Rule

Patterns reused 2+ times MUST become a layout component:

```
apps/web/src/components/layout/<LayoutName>.jsx
```

Feature folders MUST NOT contain layout components.

---

# 13. Development Environment Rules

## 13‑1. Offsite (External Network) Development

When developing outside the corporate network, some dependencies are not reachable (e.g. ADFS/OIDC, RAG, internal LLM API, POP3/mailbox).
This project supports offsite development by running a local mock via Docker Compose.

### How it works

- Use `docker-compose.dev.yml` for offsite development.
- The `adfs` service is built from `apps/adfs_dummy` (FastAPI) and provides dummy endpoints for:
  - ADFS/OIDC login/logout + discovery
  - RAG operations (`/rag/search`, `/rag/insert`, `/rag/delete`, `/rag/index-info`)
  - Mail sandbox endpoints (`/mail/*`) for local testing
- The Django `api` service loads `env/api.dev.env` to rewire auth/RAG URLs to the dummy service and to enable assistant dummy mode (`ASSISTANT_DUMMY_MODE=1`).
- Compose files expect the external Docker network `shared-net` (create once with `docker network create shared-net`).

### Agent requirements

- Do not assume corporate network connectivity for local development/tests.
- Do not hardcode intranet URLs; keep all external dependency URLs configurable via env vars.
- If you change any contract used by auth/RAG/assistant/mail flows, update the mock (`apps/adfs_dummy`) and/or the dev wiring (`env/api.dev.env`) so `docker-compose.dev.yml` remains runnable.

## 13‑2. Container‑First Testing (Mandatory)

LLM MUST:

- Run backend (Django) tests inside the Docker Compose `api` container.
- Use:
  - `docker compose -f docker-compose.dev.yml exec -T api python manage.py test ...`
  - `docker compose -f docker-compose.dev.yml exec -T api python manage.py ...`
- Avoid installing Python dependencies on the host; backend deps MUST be managed via `apps/api/requirements.txt` and baked into the `apps/api` image.

---

# ✔ End of Ultra‑Optimized LLM Constitution (Improved v2)

All LLM‑generated output MUST comply with these rules, without exception.
