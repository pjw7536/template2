// 인증과 관련된 전역 훅/컴포넌트를 lib 경로로 노출해 feature 간 의존성을 줄입니다.
export { AppAccessGate, AuthProvider, RequireAuth, useAuth, AuthAutoLoginGate, PortalAccessGate } from "@/features/auth"

export function formatProfileName(user) {
  const name = user?.username?.trim?.() || user?.displayName?.trim?.()
  const loginId = user?.knoxId?.trim?.()
  return name && loginId ? `${name}(${loginId})` : name || loginId || ""
}
