# 🧭 agents.md — Ultra‑Optimized Constitution for LLM Agents (English Edition)

### (Strict, Unambiguous, Machine‑Executable Rules)

This document defines **non‑negotiable rules** that all LLM agents MUST obey.
Every rule eliminates ambiguity, enforces determinism, and guarantees a consistent system architecture.

When uncertain, an LLM agent MUST **ask for clarification** before generating code.

---

# 1. Global Execution Rules

## 1‑1. Deterministic Behavior

LLM agents MUST:

* Follow every rule exactly.
* Produce deterministic folder paths, naming, and architecture.
* Never invent new patterns unless explicitly ordered.
* Prefer explicitness over cleverness.
* Ask whenever **any** detail is unspecified.

## 1‑2. Output Format Rules

* All code MUST be syntactically valid.
* All file paths MUST use forward slashes.
* All imports MUST resolve to real files.
* Components MUST use PascalCase.
* Hooks MUST use camelCase.
* Feature exports MUST be routed through each feature’s `index.js`.
* In `apps/web/src`, files that render JSX MUST use `.jsx` (non‑JSX modules MUST use `.js`).

---

# 2. Architectural Rules (LLM‑Strict)

## 2‑1. Vertical Slice Isolation

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

### LLM MUST obey:

* NO new folders unless explicitly allowed.
* NO nesting deeper than 2 levels.
* NO cross‑feature imports (except from another feature’s index.js).

### Allowed Imports (project‑internal only)

This rule applies to **project‑internal absolute imports**. It does NOT restrict:

* npm package imports (e.g. `react`, `react-router-dom`, `@tanstack/react-query`)
* relative imports inside the same feature (e.g. `./components/Foo.jsx`, `../utils/dateUtils.js`)

Project‑internal absolute imports MUST resolve under:

* `apps/web/src/components/ui/*` (e.g. `@/components/ui/*`, `components/ui/*`)
* `apps/web/src/components/layout/*` (e.g. `@/components/layout/*`, `components/layout/*`)
* `apps/web/src/components/common/*` (e.g. `@/components/common/*`, `components/common/*`)
* `apps/web/src/lib/*` (e.g. `@/lib/*`)
* `apps/web/src/features/<otherFeature>/index.js` (e.g. `@/features/<otherFeature>`)

Forbidden examples (must go through `<otherFeature>/index.js`):

* `apps/web/src/features/<otherFeature>/components/*`
* `apps/web/src/features/<otherFeature>/pages/*`

Anything else is **INVALID**.

---

# 3. UI Stack Rules

## 3‑1. Immutable UI Layer

LLM agents MUST NOT manually edit:

```
apps/web/src/components/ui/**/*
```

UI primitives may only be added/updated via the shadcn CLI (and only when explicitly requested).

## 3‑2. UI Assembly Hierarchy

LLM MUST assemble UI in the following order:

1. UI primitives (`components/ui/*`)
2. Layout components (`components/layout/*`)
3. Common shared components (`components/common/*`)
4. Feature‑specific UI (`features/<feature>/components/*`)

Hierarchy inversion is forbidden.

---

# 4. Routing Rules

## 4‑1. Feature Route Export

Every feature MUST expose a `routes.jsx`.

## 4‑2. Global Routes

Global routing ONLY exists under:

```
apps/web/src/routes/*
```

## 4‑3. No Business Logic in Routes

Routes MAY:

* Declare structure
* Provide element
* Validate params
* Redirect

Routes MUST NOT contain:

* Business logic
* Data logic
* Derived UI logic

---

# 5. State & Data Rules

## 5‑1. React Query Rules

React Query is the ONLY source of truth for server data.

LLM MUST:

* Use array‑based query keys.
* Avoid redundant keys.
* Invalidate the smallest necessary scope.
* NEVER mirror server data into Zustand.

## 5‑2. Zustand Rules

Zustand is ONLY allowed for:

* UI state
* Interaction flows
* Multi‑step forms
* Temporary shared state

Forbidden:

* Server data of any kind
* Redux‑like mega‑stores
* Global cross‑feature state

Store Path Rule:

```
apps/web/src/features/<feature>/store/useSomethingStore.js
```

---

# 6. Coding Rules

## 6‑1. Naming

* Components → PascalCase
* Hooks → camelCase
* Utilities → camelCase
* Zustand stores → useSomethingStore
* Pages → PascalCase
* API modules → camelCase

## 6‑2. Styling

LLM MUST:

* Use Tailwind classes only
* Use design tokens (`text-primary`, `bg-muted`, etc.)
* Use `dark:` prefix for dark mode

LLM MUST NOT:

* Use arbitrary HEX values
* Use inline styles unless strictly necessary

---

# 7. React 19 Rules

LLM MUST avoid premature optimization.

Forbidden unless required:

* useMemo
* useCallback
* React.memo

Allowed only when:

* Heavy computation exists
* Library requires identity stability

---

# 8. Backend / Django Rules (LLM‑Strict)

## 8‑1. Domain App (Feature) Isolation

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
views.py
serializers.py
services.py
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

* NO new backend folders outside the paths above.
* NO nesting deeper than 2 levels (except `migrations/` and `management/commands/`).
* NO cross‑feature imports except through another feature’s public `services.py` or `selectors.py`.
* Every concrete DB model MUST live in exactly one `<feature>/models.py`. Creating new models in `apps/api/api/models.py` is **FORBIDDEN**.
* Shared base classes/mixins MAY live in `apps/api/api/common/models.py` and MUST be `abstract = True`.
* When touching legacy root models, LLM MUST migrate them into the correct feature app (with a new migration) instead of extending the root file.

---

## 8‑2. Layer Responsibilities & Dependency Direction

The backend follows a strict, beginner‑friendly service/selector architecture.

### Responsibility

* `views.py` → HTTP only: auth/permissions, param parsing, serializer validation, calling services/selectors, returning responses.
* `serializers.py` → input/output schema + validation only.
* `permissions.py` → DRF permission classes only.
* `services.py` → **ALL** business logic and write operations (create/update/delete), transactions, external API calls.
* `selectors.py` → read‑only ORM queries (filtering, ordering, annotation). **NO side effects.**
* Views/services MUST NOT run read ORM queries directly; they MUST call selectors instead.
* `models.py` → schema + pure domain rules. **NO queries or business workflows.**

### Allowed Imports (one‑way)

This rule applies to **project‑internal imports**. Python stdlib, Django (`django.*`), and DRF (`rest_framework.*`) imports are always allowed.

* `views.py` may import: `serializers`, `permissions`, `services`, `selectors`, `api.common.*`
* `services.py` may import: `selectors`, `models`, `api.common.*`, `api.<otherFeature>.services`
* `selectors.py` may import: `models`, `api.common.*`, `api.<otherFeature>.selectors`
* `models.py` may import: Django/stdlib only, plus `api.common.*` for shared types/constants

Anything else is **INVALID**.

---

## 8‑3. Routing & API Shape

LLM MUST:

* Use versioned prefixes: `/api/v1/<feature>/...`
* Keep feature routes inside `apps/api/api/<feature>/urls.py`.
* Keep global routing ONLY in `apps/api/api/urls.py` using `include()`; global `urls.py` must NOT import feature views directly.
* `apps/api/api/urls.py` MUST be a registry only, e.g.:
  * `path("api/v1/emails/", include("api.emails.urls"))`
  * `path("api/v1/appstore/", include("api.appstore.urls"))`
* Feature `urls.py` MUST define **relative** paths (no leading `/api/v1/<feature>` inside a feature).
* Ensure routes contain **no business logic** (delegate to services/selectors).
* Name endpoints with nouns, collections plural: `emails/`, `appstore/apps/`.

---

## 8‑4. Database & Model Naming

LLM MUST:

* Use **snake_case** for fields/columns: `created_at`, `user_sdwt_prod`.
* Use singular PascalCase for model classes: `Email`, `AppStoreComment`.
* Use per‑domain table prefixes for clarity:
  * `db_table = "<feature>_<entity>"` (snake_case, singular or clear noun)
  * Examples: `emails_email`, `appstore_comment`, `account_affiliation_hierarchy`
* Set `db_table` on **every** model to enforce the prefix rule (no mixed naming).
* Primary key is `id` (BigAutoField). UUID only when an external identifier is required.
* Timestamps are UTC, timezone‑aware:
  * required: `created_at`
  * optional: `updated_at`, `deleted_at`
* Index / constraint naming:
  * `idx_<table>_<cols>`
  * `uniq_<table>_<cols>`

---

## 8‑5. Transactions & Side Effects

LLM MUST:

* Wrap multi‑step writes in `transaction.atomic()`.
* Keep external calls (RAG, email servers, etc.) inside `services.py`.
* Never perform writes inside `selectors.py` or `models.py`.

---

## 8‑6. Readability / Beginner Rules

LLM MUST:

* Prefer explicit, linear code over clever abstractions.
* Avoid metaprogramming, dynamic imports, or hidden magic.
* Keep functions/classes small and single‑purpose (≈30–50 lines max).
* Use descriptive names; avoid non‑standard abbreviations.
* Add type hints to public services and selectors.
* Put docstrings on every public service/selector explaining inputs/outputs and side effects.

---

## 8‑7. Testing & Migrations

LLM MUST:

* Add or update tests when changing business logic.
* Prefer unit tests for `services.py` and `selectors.py`; keep view tests minimal (happy + main error cases).
* Never edit an already‑applied migration; always create a new one.

---

## 8‑8. New Feature Checklist (Beginner‑Friendly)

When adding a new backend feature, LLM MUST follow this exact flow to keep code easy to read and maintain:

1. Create `apps/api/api/<feature>/` as a Django app with `__init__.py` and `apps.py` (`name = "api.<feature>"`).
2. Register the app in `apps/api/config/settings.py` → `INSTALLED_APPS`.
3. Add `models.py` with `db_table = "<feature>_<entity>"` prefixes, then create a new migration.
4. Add `serializers.py` for all request/response shapes.
5. Add `selectors.py` for all read queries.
6. Add `services.py` for all business logic and writes.
7. Add `views.py` that only wires HTTP → serializers → services/selectors.
8. Add `urls.py` with relative routes, then include it in `apps/api/api/urls.py` under `/api/v1/<feature>/`.
9. Add `tests.py` focusing on services/selectors first.

Skipping or re‑ordering these steps is **INVALID**.

# 9. File Generation Rules

When generating files, LLM MUST:

1. Output full folder path
2. Output complete file content
3. Ensure imports resolve
4. Comply with architecture
5. Follow naming rules

When updating files:

* Preserve existing structure
* Preserve exports
* Never refactor beyond the requested scope

---

# 10. Error Handling Rules

The LLM MUST ask for clarification when:

* A folder name is ambiguous
* File location is unclear
* API schemas are missing
* More than one valid interpretation exists

LLM MUST NOT guess.

---

# 11. Layout Rules (Strict for All Features)

## 11‑1. Layout Philosophy

Layout follows two universal principles:

1. Outer containers define **structure and fixed height**.
2. Avoid **nested scroll regions** on the same axis.

If multiple scroll regions are nested on the same axis → **INVALID**.

---

## 11‑2. Global Page Skeleton Rule

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

* Use `h-screen flex flex-col`
* Keep header at fixed height with `shrink-0`
* Wrap content in `flex-1 min-h-0 overflow-hidden`
* Ensure scrolling happens **inside main**, not outside

---

## 11‑3. Flex vs Grid Rules

### Flex MUST be used for:

* One‑direction layout (row/col)
* Toolbars, buttons, headers
* Alignment and distribution

### Grid MUST be used for:

* Multi‑region layouts (e.g., list + detail)
* Top‑fixed + bottom‑scroll structures
* Mixed row/column ratio layouts

---

## 11‑4. Scroll Rules

### Rule A — Only ONE scroll container per axis, per region (no nested scroll)

```jsx
<div className="min-h-0 overflow-y-auto">...</div>
```

Sibling panes may each be scrollable (see §11‑5).

### Rule B — Scrollable elements MUST have `min-h-0`

### Rule C — The official top-fixed/bottom-scroll pattern:

```jsx
<div className="grid h-full min-h-0 grid-rows-[auto,1fr]">
  <div>Fixed Area</div>
  <div className="min-h-0 overflow-y-auto">Scrollable Area</div>
</div>
```

---

## 11‑5. Two‑Pane Layout Rule

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

LLM MUST:

* Keep filter section fixed (e.g. `h-16`) or auto (`h-auto`)
* Ensure the list scrolls independently
* Ensure the detail pane scrolls independently

---

## 11‑6. Padding Responsibility Rules

### Layout components control:

* Page‑level padding (`px-4 md:px-6`)
* Section spacing (`gap-*`)
* Outer structure
* Work‑area padding

### Components control:

* Internal padding (`p-4`, `p-3`, etc.)
* Internal spacing (`gap-2`, `gap-3`)

### STRICT RULES:

LLM MUST NOT:

* Allow parent components to adjust child internal padding
* Allow child components to define page‑level padding
* Create duplicated padding across multiple layers

**Parent = external spacing.
Child = internal spacing.**
Mixing these responsibilities → **INVALID**.

---

## 11‑7. Spacing Rules

* Page padding: `p-4 md:p-6`
* Section gaps: `gap-4`
* Internal content spacing: `gap-2` or `gap-3`
* Large layout segmentation: `gap-6`

Arbitrary spacing values are forbidden.

---

## 11‑8. Layout Componentization Rule

Patterns reused 2+ times MUST become a layout component:

```
apps/web/src/components/layout/<LayoutName>.jsx
```

Feature folders MUST NOT contain layout components.

---

## 11‑9. Layout & Feature Boundary

LLM MUST:

* Place layout components in `components/layout/*`
* Place shared UI in `components/common/*`
* Place feature‑specific UI in `features/<feature>/components/*`

Mixing layout with feature UI → **INVALID**.

---

# 12. Development Environment Rules

## 12‑1. Offsite (External Network) Development

When developing outside the corporate network, some dependencies are not reachable (e.g. ADFS/OIDC, RAG, internal LLM API, POP3/mailbox).
This project supports offsite development by running a local mock via Docker Compose.

### How it works

* Use `docker-compose.dev.yml` for offsite development.
* The `adfs` service is built from `apps/adfs_dummy` (FastAPI) and provides dummy endpoints for:
  * ADFS/OIDC login/logout + discovery
  * RAG operations (`/rag/search`, `/rag/insert`, `/rag/delete`, `/rag/index-info`)
  * Mail sandbox endpoints (`/mail/*`) for local testing
* The Django `api` service loads `env/api.dev.env` to rewire auth/RAG URLs to the dummy service and to enable assistant dummy mode (`ASSISTANT_DUMMY_MODE=1`).
* Compose files expect the external Docker network `shared-net` (create once with `docker network create shared-net`).

### Agent requirements

* Do not assume corporate network connectivity for local development/tests.
* Do not hardcode intranet URLs; keep all external dependency URLs configurable via env vars.
* If you change any contract used by auth/RAG/assistant/mail flows, update the mock (`apps/adfs_dummy`) and/or the dev wiring (`env/api.dev.env`) so `docker-compose.dev.yml` remains runnable.

---

# 12‑2. Container‑First Testing (Mandatory)

LLM MUST:

* Run backend (Django) tests inside the Docker Compose `api` container (not the host Python environment).
* Use `docker compose -f docker-compose.dev.yml exec -T api python manage.py test ...` for Django tests.
* Use `docker compose -f docker-compose.dev.yml exec -T api python manage.py ...` for Django management commands.
* Avoid installing Python dependencies on the host; backend deps MUST be managed via `apps/api/requirements.txt` and baked into the `apps/api` image.

---

# ✔ End of Ultra‑Optimized LLM Constitution (English Edition)

All LLM‑generated output MUST comply with these rules, without exception.
