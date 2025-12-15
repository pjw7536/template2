import { useEffect, useRef, useState } from "react"
import { useMutation } from "@tanstack/react-query"

import { sendChatMessage } from "../api/send-chat-message"
import { normalizeChatSources } from "../utils/normalizeChatSources"

const LEGACY_DEFAULT_ROOM_ID = "default"
const MAX_HISTORY = 20
const CHAT_STORAGE_KEY = "assistant:chat-session"
const hasWindow = typeof window !== "undefined"

function createMessageId(role) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function generateRoomId() {
  return `room-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
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

      const userSdwtProd =
        typeof message.userSdwtProd === "string" && message.userSdwtProd.trim()
          ? message.userSdwtProd.trim()
          : ""

      return {
        id: message.id || createMessageId(role),
        role,
        content,
        sources: normalizeChatSources(message.sources),
        ...(userSdwtProd ? { userSdwtProd } : {}),
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
      content: "무엇을 도와드릴까요? 아래 예시는 렌더링 확인용 더미입니다.",
    },
    {
      id: createMessageId("assistant"),
      role: "assistant",
      content: [
        "줄바꿈 예시:",
        "첫 줄<br>둘째 줄",
        "",
        "테이블 예시:",
        "| 단계 | 설명 |",
        "| --- | --- |",
        "| 1 | 줄바꿈 확인 |",
        "| 2 | 테이블 확인 |",
        "",
        "리스트와 코드:",
        "- 목록 1",
        "- 목록 2",
        "",
        "인라인 코드 `code` 와 블록:",
        "```js",
        "console.log('markdown 렌더링 테스트');",
        "```",
      ].join("\n"),
    },
  ]
}

function trimMessages(messages, limit = MAX_HISTORY) {
  if (!Array.isArray(messages)) return []
  if (messages.length <= limit) return messages
  return messages.slice(-limit)
}

function persistChatSession({ rooms, messagesByRoom, activeRoomId }) {
  if (!hasWindow) return

  try {
    const trimmedMessagesByRoom = rooms.reduce((acc, room) => {
      const roomMessages = messagesByRoom?.[room.id]
      acc[room.id] = trimMessages(normalizeMessages(roomMessages))
      return acc
    }, {})

    const payload = {
      rooms,
      messagesByRoom: trimmedMessagesByRoom,
      activeRoomId,
      version: 1,
    }

    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(payload))
  } catch (error) {
    console.error("Failed to persist assistant chat session", error)
  }
}

function loadPersistedSession() {
  if (!hasWindow) return null

  try {
    const raw = window.localStorage.getItem(CHAT_STORAGE_KEY)
    if (!raw) return null

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return null

    const rooms = normalizeRooms(parsed.rooms)
    if (rooms.length === 0) return null

    const storedMessagesByRoom =
      parsed.messagesByRoom && typeof parsed.messagesByRoom === "object"
        ? parsed.messagesByRoom
        : {}

    const messagesByRoom = rooms.reduce((acc, room) => {
      acc[room.id] = buildInitialMessages(storedMessagesByRoom[room.id])
      return acc
    }, {})

    const activeRoomId = rooms.some((room) => room.id === parsed.activeRoomId)
      ? parsed.activeRoomId
      : rooms[0].id

    return {
      initialRooms: rooms,
      initialMessagesByRoom: messagesByRoom,
      initialActiveRoomId: activeRoomId,
    }
  } catch (error) {
    console.error("Failed to load assistant chat session", error)
    return null
  }
}

function mergeInitialOptions(persisted, provided) {
  const base = persisted && typeof persisted === "object" ? persisted : {}
  if (!provided || typeof provided !== "object") {
    return { ...base }
  }

  const merged = { ...base }
  const keys = ["initialRooms", "initialMessages", "initialMessagesByRoom", "initialActiveRoomId"]
  keys.forEach((key) => {
    if (provided[key] !== undefined) {
      merged[key] = provided[key]
    }
  })

  return merged
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
  const persisted = loadPersistedSession()
  const resolvedOptions = mergeInitialOptions(persisted, options)
  const { initialRooms, initialMessages, initialMessagesByRoom, initialActiveRoomId } = resolvedOptions

  const messagesMap =
    initialMessagesByRoom && typeof initialMessagesByRoom === "object" ? initialMessagesByRoom : {}

  const normalizedRooms = normalizeRooms(initialRooms).filter((room) => room.id !== LEGACY_DEFAULT_ROOM_ID)

  const messagesByRoom = {}

  normalizedRooms.forEach((room) => {
    const seed = messagesMap[room.id] ?? initialMessages
    messagesByRoom[room.id] = buildInitialMessages(seed)
  })

  const legacyDefaultMessages = normalizeMessages(messagesMap[LEGACY_DEFAULT_ROOM_ID])
  const hasLegacyConversation = legacyDefaultMessages.some((message) => message.role === "user")
  const normalizedInitialMessages = normalizeMessages(initialMessages)
  const hasInitialMessages = normalizedInitialMessages.length > 0

  if (normalizedRooms.length === 0 && (hasLegacyConversation || hasInitialMessages)) {
    const migratedRoomId = generateRoomId()
    normalizedRooms.push({
      id: migratedRoomId,
      name: hasLegacyConversation ? "이전 대화" : "새 대화",
    })
    messagesByRoom[migratedRoomId] = buildInitialMessages(
      hasLegacyConversation ? legacyDefaultMessages : normalizedInitialMessages,
    )
  } else if (hasLegacyConversation) {
    const migratedRoomId = generateRoomId()
    normalizedRooms.push({ id: migratedRoomId, name: "이전 대화" })
    messagesByRoom[migratedRoomId] = buildInitialMessages(legacyDefaultMessages)
  }

  const activeRoomId =
    typeof initialActiveRoomId === "string" && normalizedRooms.some((room) => room.id === initialActiveRoomId)
      ? initialActiveRoomId
      : normalizedRooms[0]?.id || null

  return { rooms: normalizedRooms, messagesByRoom, activeRoomId }
}

export function useChatSession(options = {}) {
  const userSdwtProd = typeof options?.userSdwtProd === "string" ? options.userSdwtProd.trim() : ""
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

  const roomExists = (roomId) => rooms.some((room) => room.id === roomId)

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
    const id = generateRoomId()
    setRooms((prev) => {
      const name = fallbackName || `새 대화 ${prev.length + 1}`
      return [...prev, { id, name }]
    })
    setMessagesByRoom((prev) => ({ ...prev, [id]: buildInitialMessages() }))
    setActiveRoomId(id)
    setErrorMessage("")
    return id
  }

  const getOrCreateActiveRoomId = (preferredRoomId) => {
    if (preferredRoomId) {
      ensureRoomExists(preferredRoomId)
      setActiveRoomId(preferredRoomId)
      return preferredRoomId
    }

    if (activeRoomId && roomExists(activeRoomId)) {
      return activeRoomId
    }

    if (rooms.length > 0) {
      const fallbackId = rooms[0].id
      setActiveRoomId(fallbackId)
      return fallbackId
    }

    return createRoom()
  }

  const resetConversation = (roomId = activeRoomId) => {
    const targetRoomId = getOrCreateActiveRoomId(roomId)
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

    const roomId = getOrCreateActiveRoomId()
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
        userSdwtProd,
      })

      const reply =
        typeof result?.reply === "string" && result.reply.trim()
          ? result.reply.trim()
          : "답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요."
      const sources = normalizeChatSources(result?.sources)
      const segments = Array.isArray(result?.segments) ? result.segments : []
      const normalizedSegments = segments
        .map((segment) => {
          if (!segment || typeof segment !== "object") return null
          const segmentReply =
            typeof segment.reply === "string" && segment.reply.trim() ? segment.reply.trim() : null
          if (!segmentReply) return null
          return {
            id: createMessageId("assistant"),
            role: "assistant",
            content: segmentReply,
            sources: normalizeChatSources(segment.sources),
            ...(userSdwtProd ? { userSdwtProd } : {}),
          }
        })
        .filter(Boolean)

      setMessagesByRoom((prev) => {
        const baseMessages = prev[roomId] ?? []
        if (normalizedSegments.length > 0) {
          return {
            ...prev,
            [roomId]: trimMessages([...baseMessages, ...normalizedSegments]),
          }
        }

        return {
          ...prev,
          [roomId]: trimMessages([
            ...baseMessages,
            {
              id: createMessageId("assistant"),
              role: "assistant",
              content: reply,
              sources,
              ...(userSdwtProd ? { userSdwtProd } : {}),
            },
          ]),
        }
      })
    } catch (error) {
      setErrorMessage(error?.message || "메시지를 전송하지 못했어요.")
    }
  }

  const removeRoom = (roomId) => {
    if (!roomId) return

    setRooms((prevRooms) => {
      const remainingRooms = prevRooms.filter((room) => room.id !== roomId)
      if (remainingRooms.length === prevRooms.length) return prevRooms

      if (remainingRooms.length === 0) {
        const fallbackId = generateRoomId()
        const fallbackRoom = { id: fallbackId, name: "새 대화" }
        setMessagesByRoom((prevMessages) => {
          const nextMessages = { ...prevMessages }
          delete nextMessages[roomId]
          nextMessages[fallbackId] = buildInitialMessages()
          return nextMessages
        })
        setActiveRoomId(fallbackId)
        return [fallbackRoom]
      }

      setMessagesByRoom((prevMessages) => {
        const nextMessages = { ...prevMessages }
        delete nextMessages[roomId]
        return nextMessages
      })
      setActiveRoomId((prevActive) => (prevActive === roomId ? remainingRooms[0].id : prevActive))
      return remainingRooms
    })
  }

  useEffect(() => {
    persistChatSession({ rooms, messagesByRoom, activeRoomId })
  }, [rooms, messagesByRoom, activeRoomId])

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
    removeRoom,
  }
}
