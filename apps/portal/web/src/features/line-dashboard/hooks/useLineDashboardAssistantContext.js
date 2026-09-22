import { useEffect } from "react"

import { usePageAssistantContext } from "@/lib/assistant/pageContext"

const LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY = "line-dashboard:v1"

export function useLineDashboardAssistantContext({
  view,
  lineId,
  from,
  to,
  lineFilterMode,
  recentHoursStart,
  recentHoursEnd,
}) {
  const { registerPageContext, clearPageContext } = usePageAssistantContext()

  useEffect(() => {
    const normalizedLineId = typeof lineId === "string" ? lineId.trim() : ""
    if (!normalizedLineId || !["status", "history"].includes(view)) {
      clearPageContext(LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY)
      return undefined
    }
    const scope = {
      view,
      lineId: normalizedLineId,
      from,
      to,
      ...(view === "status"
        ? { lineFilterMode, recentHoursStart, recentHoursEnd }
        : {}),
    }
    registerPageContext({
      kind: "line-dashboard",
      key: LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY,
      scope,
    })
    return () => clearPageContext(LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY)
  }, [
    clearPageContext,
    from,
    lineFilterMode,
    lineId,
    recentHoursEnd,
    recentHoursStart,
    registerPageContext,
    to,
    view,
  ])
}
