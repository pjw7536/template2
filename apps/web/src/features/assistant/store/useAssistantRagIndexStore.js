import { create } from "zustand"

function normalizeUserSdwtProd(value) {
  return typeof value === "string" ? value.trim() : ""
}

export const useAssistantRagIndexStore = create((set) => ({
  userSdwtProd: "",
  setUserSdwtProd: (nextValue) =>
    set({ userSdwtProd: normalizeUserSdwtProd(nextValue) }),
}))

