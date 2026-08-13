import { useEffect } from "react"

import { usePageAssistantContext } from "@/lib/assistant/pageContext"

const APPSTORE_ASSISTANT_CONTEXT_KEY = "appstore:v1"

export function useAppstoreAssistantContext({ query, category, selectedAppId }) {
  const { registerPageContext, clearPageContext } = usePageAssistantContext()

  useEffect(() => {
    registerPageContext({
      kind: "appstore",
      key: APPSTORE_ASSISTANT_CONTEXT_KEY,
      scope: {
        query: typeof query === "string" ? query : "",
        category: typeof category === "string" ? category : "all",
        selectedAppId: selectedAppId ?? null,
      },
    })
    return () => clearPageContext(APPSTORE_ASSISTANT_CONTEXT_KEY)
  }, [category, clearPageContext, query, registerPageContext, selectedAppId])
}
