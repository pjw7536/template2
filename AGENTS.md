아래 aent.md 평가해줘
# 🧭 agents.md — Ultra-Optimized Constitution for LLM Agents

### (Strict, Unambiguous, Machine-Executable Rules)

This document defines **non-negotiable rules** for LLM agents.
Every rule is written to eliminate ambiguity, ensure deterministic outputs, and produce consistent architecture aligned with the project.

LLM agents **MUST** obey every rule exactly.
If uncertain, the agent **MUST ask for clarification** before generating code.

---

# 1. Global Execution Rules

## 1-1. Deterministic Behavior

LLM agents **MUST**:

* Follow every rule in this document exactly.
* Produce consistent folder paths, naming, and architecture.
* Never invent new patterns unless explicitly ordered.
* Prefer explicitness over cleverness.
* Ask when **any detail is unspecified**.

## 1-2. Output Format Rules

* Code MUST be syntactically valid.
* File paths MUST always use forward slashes.
* Imports MUST be real and resolvable within this architecture.
* Components MUST follow PascalCase.
* Hooks MUST follow camelCase.
* Feature exports MUST pass through each feature's `index.js`.

---

# 2. Architectural Rules (LLM-Strict)

## 2-1. Vertical Slice Isolation

LLM agents **MUST** generate features that are fully isolated.

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

* No additional folders.
* No deeper nesting beyond 2 levels.
* No cross-feature internal imports.

### Allowed Imports ONLY:

* `apps/web/src/components/ui/*`
* `apps/web/src/components/layout/*`
* `apps/web/src/components/common/*`
* `apps/web/src/lib/*`
* `apps/web/src/features/<otherFeature>/index.js` **ONLY**

If an LLM agent attempts to import from any deeper path inside another feature → **INVALID**.

---

# 3. UI Stack Rules

## 3-1. Immutable UI Layer

LLM agents **MUST NOT** modify files inside:

```
apps/web/src/components/ui/**/*
```

All new UI primitives MUST be added via shadcn CLI, not handwritten.

## 3-2. UI Assembly Hierarchy

LLM agents MUST structure UI in this order:

1. UI primitives (`components/ui/*`)
2. Layout (`components/layout/*`)
3. Common shared components (`components/common/*`)
4. Feature-specific UI

LLM MUST NOT invert this layering.

---

# 4. Routing Rules

## 4-1. Feature Route Export

Every feature MUST include a `routes.jsx` exporting route config.

## 4-2. Global Routes

Global routing MUST exist only inside:

```
apps/web/src/routes/*
```

## 4-3. No Business Logic in Routes

Routes can only:

* Define structure
* Define element
* Validate params
* Redirect

Routes MUST NOT contain:

* Data logic
* Business logic
* Derived UI logic

---

# 5. State & Data Rules

## 5-1. React Query Rules

React Query is the **ONLY** source of truth for server data.

LLM MUST:

* Use array-based query keys.
* Avoid redundant or duplicated keys.
* Invalidate only minimal scopes.
* Never duplicate Query data into Zustand.

## 5-2. Zustand Rules (Strict for LLM)

Allowed ONLY for:

* UI state
* Interaction flows
* Multi-step forms
* Temporary shared state

LLM MUST NOT:

* Store server data in Zustand.
* Recreate Redux-style global stores.
* Build mega-stores.

### Store Path Rules

```
apps/web/src/features/<feature>/store/useSomethingStore.js
```

Cross-feature stores MUST get explicit human approval.

---

# 6. Coding Rules

## 6-1. Naming

* Components → PascalCase
* Hooks → camelCase
* Utilities → camelCase
* Zustand stores → `useSomethingStore`
* Pages → PascalCase
* API modules → camelCase

## 6-2. Styling

LLM MUST use:

* Tailwind classnames
* Design tokens only (`text-primary`, `bg-muted`, etc.)
* Dark mode via `dark:` prefix

LLM MUST NOT:

* Use raw HEX colors
* Use inline styles unless required

---

# 7. React 19 Rules (Strict for LLM)

LLM MUST avoid memoization unless explicitly required.

Forbidden:

* `useMemo` for simple derived values
* `useCallback` for avoiding re-renders
* `React.memo` unless performance-critical

Allowed only when:

* Heavy computation exists
* Library requires stable identity

---

# 8. Backend / Django Rules

LLM MUST:

* Use `/api/v1/<feature>` prefix
* Not import models across apps directly
* Use service layer for domain logic
* Store all timestamps in UTC

---

# 9. File Generation Rules

When generating new code, LLM MUST:

1. Generate the full folder path.
2. Output the complete file content.
3. Ensure imports resolve.
4. Ensure it follows the architecture.
5. Use consistent naming.

When updating existing files, LLM MUST:

* Keep existing architecture
* Maintain exports
* Avoid refactoring outside the requested scope

---

# 10. LLM Error Handling Rules

LLM MUST ask for clarification when:

* A folder name is ambiguous
* File placement isn't obvious
* API schemas are missing
* There is more than one valid interpretation

LLM MUST NOT guess.

---

# ✔ End of Ultra-Optimized LLM Constitution

These rules are absolute.
All LLM-generated contributions MUST comply without exception.
