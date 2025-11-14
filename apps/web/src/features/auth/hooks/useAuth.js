// src/features/auth/hooks/useAuth.js
// AuthContext를 안전하게 꺼내 쓰기 위한 커스텀 훅입니다.

import { useContext } from "react"

import { AuthContext } from "../context/AuthContext"

/**
 * useAuth
 * ---------------------------------------------------------------------------
 * - Provider 내부가 아닐 때 실수로 호출하면 명확한 오류 메시지를 띄워 줍니다.
 * - 컴포넌트에서는 const { user } = useAuth() 형태로 간단히 사용합니다.
 */
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuth는 AuthProvider 내부에서만 사용할 수 있습니다.")
  }
  return ctx
}
