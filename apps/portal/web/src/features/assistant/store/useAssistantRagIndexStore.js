import { create } from "zustand"

function normalizeList(values) {
  if (!Array.isArray(values)) return []
  const normalized = values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

export const useAssistantRagIndexStore = create((set) => ({
  permissionGroups: [],
  ragIndexNames: [],
  permissionGroupsSource: "default",
  ragIndexNamesSource: "default",
  setPermissionGroups: (nextValue, source = "user") =>
    set({
      permissionGroups: normalizeList(nextValue),
      permissionGroupsSource: source,
    }),
  setRagIndexNames: (nextValue, source = "user") =>
    set({
      ragIndexNames: normalizeList(nextValue),
      ragIndexNamesSource: source,
    }),
}))
