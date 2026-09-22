import { useEffect } from "react"

import { usePageAssistantContext } from "@/lib/assistant/pageContext"

export function useEmailAssistantContext({ scope, mailbox, emailId }) {
  const { registerPageContext, clearPageContext } = usePageAssistantContext()

  useEffect(() => {
    const normalizedMailbox = typeof mailbox === "string" ? mailbox.trim() : ""
    if (!normalizedMailbox) return undefined
    const normalizedEmailId = String(emailId || "").trim()
    registerPageContext({
      key: "emails:v1",
      kind: "emails",
      label: scope === "sent" ? "보낸 메일함" : `${normalizedMailbox} 메일함`,
      description: normalizedEmailId
        ? "현재 메일함과 선택한 메일을 범위로 사용합니다."
        : "현재 메일함을 범위로 사용합니다.",
      scope: {
        mailbox: normalizedMailbox,
        ...(normalizedEmailId ? { emailId: normalizedEmailId } : {}),
      },
    })
    return () => clearPageContext("emails:v1")
  }, [clearPageContext, emailId, mailbox, registerPageContext, scope])
}
