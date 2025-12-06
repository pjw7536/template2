import { useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { sendChatMessage } from "../api/send-chat-message"

function createMessageId(role) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return []

  return messages
    .map((message) => {
      if (!message) return null
      const role = typeof message.role === "string" ? message.role : undefined
      const content =
        typeof message.content === "string" && message.content.trim()
          ? message.content.trim()
          : undefined

      if (!role || !content) return null

      return {
        id: message.id || createMessageId(role),
        role,
        content,
      }
    })
    .filter(Boolean)
}

function buildInitialMessages(initialMessages) {
  const normalized = normalizeMessages(initialMessages)
  if (normalized.length > 0) return normalized

  return [
    {
      id: createMessageId("assistant"),
      role: "assistant",
      content: "무엇을 도와드릴까요? 궁금한 점을 입력하면 바로 답변해드릴게요.",
    },
  ]
}

export function useChatSession({ initialMessages } = {}) {
  const [messages, setMessages] = useState(() => buildInitialMessages(initialMessages))
  const [errorMessage, setErrorMessage] = useState("")

  const mutation = useMutation({
    mutationFn: sendChatMessage,
  })

  const isSending = mutation.isPending

  const resetConversation = () => {
    setMessages(buildInitialMessages())
    setErrorMessage("")
    mutation.reset()
  }

  const sendMessage = async (input) => {
    const text = typeof input === "string" ? input.trim() : ""

    if (!text) {
      setErrorMessage("보낼 메시지를 입력해주세요.")
      return
    }

    if (isSending) return

    setErrorMessage("")

    let historyForRequest = []
    setMessages((prev) => {
      const userMessage = { id: createMessageId("user"), role: "user", content: text }
      const nextMessages = [...prev, userMessage]
      historyForRequest = nextMessages
      return nextMessages
    })

    try {
      const result = await mutation.mutateAsync({
        prompt: text,
        history: historyForRequest.map(({ role, content }) => ({ role, content })),
      })

      const reply =
        typeof result?.reply === "string" && result.reply.trim()
          ? result.reply.trim()
          : "답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요."

      setMessages((prev) => [
        ...prev,
        { id: createMessageId("assistant"), role: "assistant", content: reply },
      ])
    } catch (error) {
      setErrorMessage(error?.message || "메시지를 전송하지 못했어요.")
    }
  }

  return {
    messages,
    isSending,
    errorMessage,
    clearError: () => setErrorMessage(""),
    sendMessage,
    resetConversation,
  }
}
