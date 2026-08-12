export function isEmailAssistantRoute(pathname) {
  if (typeof pathname !== "string") return false
  const normalizedPath = pathname.replace(/\/+$/, "").toLowerCase()
  return normalizedPath === "/emails" || normalizedPath.startsWith("/emails/")
}
