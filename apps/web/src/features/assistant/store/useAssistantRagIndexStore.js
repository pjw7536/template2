import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

const STORAGE_KEY = "assistant:rag-settings"

function normalizeList(values) {
  if (!Array.isArray(values)) return []
  const normalized = values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

export const useAssistantRagIndexStore = create(
  persist(
    (set) => ({
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
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        permissionGroups: state.permissionGroups,
        ragIndexNames: state.ragIndexNames,
        permissionGroupsSource: state.permissionGroupsSource,
        ragIndexNamesSource: state.ragIndexNamesSource,
      }),
    },
  ),
)
