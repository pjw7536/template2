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

### Allowed Imports ONLY:

* `apps/web/src/components/ui/*`
* `apps/web/src/components/layout/*`
* `apps/web/src/components/common/*`
* `apps/web/src/lib/*`
* `apps/web/src/features/<otherFeature>/index.js`

Anything else is **INVALID**.

---

# 3. UI Stack Rules

## 3‑1. Immutable UI Layer

LLM agents MUST NOT modify:

```
apps/web/src/components/ui/**/*
```

All new UI primitives MUST come from shadcn CLI.

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

# 8. Backend / Django Rules

LLM MUST:

* Use `/api/v1/<feature>` prefix
* Never import models across Django apps
* Place business logic inside service layer
* Store timestamps in UTC

---

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
2. **Scroll MUST occur in exactly one element per axis.**

If multiple scroll regions appear on the same axis → **INVALID**.

---

## 11‑2. Global Page Skeleton Rule

Every page MUST follow this layout skeleton:

```tsx
<div class="h-screen flex flex-col">
  <header class="h-16 shrink-0">...</header>

  <main class="flex-1 min-h-0 overflow-hidden">
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

### Rule A — Only ONE scroll container per axis

```tsx
<div class="min-h-0 overflow-y-auto">...</div>
```

### Rule B — Scrollable elements MUST have `min-h-0`

### Rule C — The official top-fixed/bottom-scroll pattern:

```tsx
<div class="grid h-full min-h-0 grid-rows-[auto,1fr]">
  <div>Fixed Area</div>
  <div class="min-h-0 overflow-y-auto">Scrollable Area</div>
</div>
```

---

## 11‑5. Two‑Pane Layout Rule

(Left list + Right detail)

```tsx
<div class="grid flex-1 min-h-0 gap-4 md:grid-cols-2">
  <div class="grid min-h-0 grid-rows-[auto,1fr] gap-2">
    <div class="h-[auto or fixed] overflow-hidden">{filters}</div>
    <div class="min-h-0 overflow-y-auto">{list}</div>
  </div>

  <div class="min-h-0 overflow-y-auto">{detail}</div>
</div>
```

LLM MUST:

* Keep filter section fixed or auto
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

# ✔ End of Ultra‑Optimized LLM Constitution (English Edition)

All LLM‑generated output MUST comply with these rules, without exception.
