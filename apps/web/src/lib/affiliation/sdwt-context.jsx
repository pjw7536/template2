import * as React from "react"

const SdwtContext = React.createContext(null)

function normalizeSdwt(value) {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value.trim()
  return String(value).trim()
}

export function SdwtProvider({ children, userSdwtProd = "", onChange }) {
  const resolvedSdwt = normalizeSdwt(userSdwtProd)
  const setUserSdwtProd = typeof onChange === "function" ? onChange : () => {}

  return (
    <SdwtContext.Provider value={{ userSdwtProd: resolvedSdwt, setUserSdwtProd }}>
      {children}
    </SdwtContext.Provider>
  )
}

export function useSdwt() {
  const context = React.useContext(SdwtContext)
  if (!context) {
    throw new Error("useSdwt must be used within a SdwtProvider")
  }
  return context
}
