import { useEffect, useRef, useState } from "react"

import { sortRoomsByRecentQuestion } from "../utils/chatRooms"
import { useChatSession } from "./useChatSession"

export function useAssistantChatController({
  sessionOptions,
  isSurfaceActive = true,
}) {
  const session = useChatSession(sessionOptions)
  const [input, setInput] = useState("")
  const inputRef = useRef(null)
  const wasSendingRef = useRef(false)

  useEffect(() => {
    if (isSurfaceActive) inputRef.current?.focus()
  }, [isSurfaceActive])

  useEffect(() => {
    if (!isSurfaceActive) {
      wasSendingRef.current = session.isSending
      return
    }
    if (!session.isSending && wasSendingRef.current) inputRef.current?.focus()
    wasSendingRef.current = session.isSending
  }, [isSurfaceActive, session.isSending])

  const focusInput = () => inputRef.current?.focus()

  const submitMessage = async (event) => {
    event.preventDefault()
    if (!input.trim() || session.isSending) return
    try {
      const result = await session.sendMessage(input)
      if (result?.ok) setInput("")
    } finally {
      focusInput()
    }
  }

  return {
    ...session,
    focusInput,
    input,
    inputRef,
    setInput,
    submitMessage,
    sortedRooms: sortRoomsByRecentQuestion(
      session.roomListRooms,
      session.messagesByRoom,
    ),
  }
}
