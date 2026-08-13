import { useEffect } from "react"

import { usePageAssistantContext } from "@/lib/assistant/pageContext"

const LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY = "line-dashboard:v1"

export function useLineDashboardAssistantContext({ view, lineId, from, to }) {
  const { registerPageContext, clearPageContext } = usePageAssistantContext()

  useEffect(() => {
    const normalizedLineId = typeof lineId === "string" ? lineId.trim() : ""
    if (!normalizedLineId) {
      clearPageContext(LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY)
      return undefined
    }
    registerPageContext({
      kind: "line-dashboard",
      key: LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY,
      scope: {
        view: view === "history" ? "history" : "status",
        lineId: normalizedLineId,
        ...(from ? { from } : {}),
        ...(to ? { to } : {}),
      },
    })
    return () => clearPageContext(LINE_DASHBOARD_ASSISTANT_CONTEXT_KEY)
  }, [clearPageContext, from, lineId, registerPageContext, to, view])
}
