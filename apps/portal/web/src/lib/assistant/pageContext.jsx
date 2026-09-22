import { createContext, useCallback, useContext, useMemo, useState } from "react"

const EMPTY_PAGE_ASSISTANT_CONTEXT = {
  pageContext: null,
  registerPageContext: () => {},
  clearPageContext: () => {},
}

const PageAssistantContext = createContext(EMPTY_PAGE_ASSISTANT_CONTEXT)

export function PageAssistantContextProvider({ children }) {
  const [pageContext, setPageContext] = useState(null)

  const registerPageContext = useCallback((nextContext) => {
    setPageContext(nextContext || null)
  }, [])

  const clearPageContext = useCallback((contextKey) => {
    setPageContext((currentContext) => {
      if (!contextKey || currentContext?.key === contextKey) return null
      return currentContext
    })
  }, [])

  const value = useMemo(
    () => ({ pageContext, registerPageContext, clearPageContext }),
    [clearPageContext, pageContext, registerPageContext],
  )

  return <PageAssistantContext.Provider value={value}>{children}</PageAssistantContext.Provider>
}

export function usePageAssistantContext() {
  return useContext(PageAssistantContext)
}
