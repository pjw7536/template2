import { useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { sendChatMessage } from "../api/send-chat-message"

const DEFAULT_ROOM_ID = "default"
const MAX_HISTORY = 20

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
  if (normalized.length > 0) return normalized.slice(-MAX_HISTORY)

  return [
    {
      id: createMessageId("assistant"),
      role: "assistant",
      content: "무엇을 도와드릴까요? 궁금한 점을 입력하면 바로 답변해드릴게요.",
    },
  ]
}

function trimMessages(messages, limit = MAX_HISTORY) {
  if (!Array.isArray(messages)) return []
  if (messages.length <= limit) return messages
  return messages.slice(-limit)
}

function normalizeRooms(rawRooms) {
  if (!Array.isArray(rawRooms)) return []

  return rawRooms
    .map((room, index) => {
      const id = typeof room?.id === "string" ? room.id.trim() : ""
      if (!id) return null
      const name =
        typeof room?.name === "string" && room.name.trim()
          ? room.name.trim()
          : `대화 ${index + 1}`
      return { id, name }
    })
    .filter(Boolean)
}

function buildInitialState(options = {}) {
  const { initialRooms, initialMessages, initialMessagesByRoom, initialActiveRoomId } = options
  const defaultRoom = { id: DEFAULT_ROOM_ID, name: "기본 대화" }

  const rooms = normalizeRooms(initialRooms)
  const hasDefault = rooms.some((room) => room.id === defaultRoom.id)
  const normalizedRooms = hasDefault ? rooms : [defaultRoom, ...rooms]

  const messagesByRoom = {}
  const messagesMap = initialMessagesByRoom && typeof initialMessagesByRoom === "object" ? initialMessagesByRoom : {}

  normalizedRooms.forEach((room) => {
    const roomMessages = messagesMap[room.id]
    const seed = room.id === DEFAULT_ROOM_ID ? roomMessages ?? initialMessages : roomMessages
    messagesByRoom[room.id] = buildInitialMessages(seed)
  })

  const candidateActiveRoom =
    typeof initialActiveRoomId === "string" && normalizedRooms.some((room) => room.id === initialActiveRoomId)
      ? initialActiveRoomId
      : normalizedRooms[0].id

  return { rooms: normalizedRooms, messagesByRoom, activeRoomId: candidateActiveRoom }
}

export function useChatSession(options = {}) {
  const initialRef = useRef(null)
  if (!initialRef.current) {
    initialRef.current = buildInitialState(options)
  }

  const [rooms, setRooms] = useState(initialRef.current.rooms)
  const [messagesByRoom, setMessagesByRoom] = useState(initialRef.current.messagesByRoom)
  const [activeRoomId, setActiveRoomId] = useState(initialRef.current.activeRoomId)
  const [errorMessage, setErrorMessage] = useState("")

  const mutation = useMutation({
    mutationFn: sendChatMessage,
  })

  const isSending = mutation.isPending

  const messages = messagesByRoom[activeRoomId] || buildInitialMessages()

  const ensureRoomExists = (roomId) => {
    if (!roomId) return
    setRooms((prev) => {
      if (prev.some((room) => room.id === roomId)) return prev
      return [...prev, { id: roomId, name: roomId }]
    })
    setMessagesByRoom((prev) => {
      if (prev[roomId]) return prev
      return { ...prev, [roomId]: buildInitialMessages() }
    })
  }

  const selectRoom = (roomId) => {
    if (!roomId) return
    ensureRoomExists(roomId)
    setActiveRoomId(roomId)
    setMessagesByRoom((prev) => {
      if (prev[roomId]) return prev
      return { ...prev, [roomId]: buildInitialMessages() }
    })
    setErrorMessage("")
  }

  const createRoom = (label) => {
    const fallbackName = typeof label === "string" && label.trim() ? label.trim() : null
    const id = `room-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
    setRooms((prev) => {
      const name = fallbackName || `새 대화 ${prev.length + 1}`
      return [...prev, { id, name }]
    })
    setMessagesByRoom((prev) => ({ ...prev, [id]: buildInitialMessages() }))
    setActiveRoomId(id)
    setErrorMessage("")
  }

  const resetConversation = (roomId = activeRoomId) => {
    const targetRoomId = roomId || DEFAULT_ROOM_ID
    ensureRoomExists(targetRoomId)
    setMessagesByRoom((prev) => ({ ...prev, [targetRoomId]: buildInitialMessages() }))
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

    const roomId = activeRoomId || DEFAULT_ROOM_ID
    let historyForRequest = []
    setMessagesByRoom((prev) => {
      const current = prev[roomId] ?? buildInitialMessages()
      const userMessage = { id: createMessageId("user"), role: "user", content: text }
      const nextMessages = trimMessages([...current, userMessage])
      historyForRequest = nextMessages
      return { ...prev, [roomId]: nextMessages }
    })

    try {
      const result = await mutation.mutateAsync({
        prompt: text,
        history: historyForRequest.map(({ role, content }) => ({ role, content })),
        roomId,
      })

      const reply =
        typeof result?.reply === "string" && result.reply.trim()
          ? result.reply.trim()
          : "답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요."

      setMessagesByRoom((prev) => ({
        ...prev,
        [roomId]: trimMessages([
          ...(prev[roomId] ?? []),
          { id: createMessageId("assistant"), role: "assistant", content: reply },
        ]),
      }))
    } catch (error) {
      setErrorMessage(error?.message || "메시지를 전송하지 못했어요.")
    }
  }

  return {
    rooms,
    activeRoomId,
    messages,
    messagesByRoom,
    isSending,
    errorMessage,
    clearError: () => setErrorMessage(""),
    sendMessage,
    resetConversation,
    selectRoom,
    createRoom,
  }
}
