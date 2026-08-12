import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  abandonAssistantGeneration,
  acquireAssistantGeneration,
  appendAssistantConversationMessages,
  clearAssistantConversationMessages,
  createAssistantConversation,
  deleteAssistantMessageFeedback,
  deleteAssistantConversation,
  exportAssistantConversation,
  fetchAssistantConversationMessagePage,
  fetchAssistantConversationPage,
  finalizeAssistantGeneration,
  generateAssistantConversationTitle,
  refreshAssistantConversationSummary,
  submitAssistantMessageFeedback,
  updateAssistantConversation,
} from "../api/conversationApi"
import { sendChatMessage } from "../api/sendChatMessage"
import {
  MAX_ASSISTANT_MESSAGE_CHARS,
  normalizeGeneratedAssistantMessage,
} from "../utils/chatLimits"
import { sortRoomsByRecentQuestion } from "../utils/chatRooms"
import {
  formatChatHistoryContent,
  isSameChatMemory,
} from "../utils/chatMemory"
import { normalizeChatSources } from "../utils/normalizeChatSources"

const MAX_MODEL_HISTORY = 20
const DEFAULT_ROOM_NAME_PATTERN = /^새 대화(?:\s+\d+)?$/

function normalizeList(values) {
  if (!Array.isArray(values)) return []
  return Array.from(
    new Set(
      values
        .map((value) => (typeof value === "string" ? value.trim() : ""))
        .filter(Boolean),
    ),
  )
}

function resolvePrimaryMailbox(permissionGroups) {
  const normalized = normalizeList(permissionGroups)
  return normalized.find((group) => group !== "rag-public") || normalized[0] || ""
}

function createMessageId(role) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function generateLocalRoomId() {
  return `room-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}

function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return []
  return messages
    .map((message) => {
      const role = typeof message?.role === "string" ? message.role : ""
      const content = typeof message?.content === "string" ? message.content.trim() : ""
      if (!role || !content) return null
      const contextKey =
        typeof message.contextKey === "string" && message.contextKey.trim()
          ? message.contextKey.trim()
          : ""
      const userSdwtProd =
        typeof message.userSdwtProd === "string" ? message.userSdwtProd.trim() : ""
      const createdAt =
        typeof message.createdAt === "string" && message.createdAt
          ? message.createdAt
          : undefined
      const streamId =
        typeof message.streamId === "string" && message.streamId.trim()
          ? message.streamId.trim()
        : undefined
      const isGreeting = message.isGreeting === true
      return {
        id: message.id || createMessageId(role),
        role,
        content,
        sources: normalizeChatSources(message.sources),
        ...(contextKey ? { contextKey } : {}),
        ...(userSdwtProd ? { userSdwtProd } : {}),
        ...(createdAt ? { createdAt } : {}),
        ...(streamId ? { streamId } : {}),
        ...(isGreeting ? { isGreeting: true } : {}),
        ...(message.parentId ? { parentId: message.parentId } : {}),
        ...(message.revisionOfId ? { revisionOfId: message.revisionOfId } : {}),
        ...(message.generationId ? { generationId: message.generationId } : {}),
        ...(message.contextSnapshot ? { contextSnapshot: message.contextSnapshot } : {}),
        ...(message.feedback ? { feedback: message.feedback } : {}),
      }
    })
    .filter(Boolean)
}

function buildInitialMessages(messages, { animateGreeting = false } = {}) {
  const normalized = normalizeMessages(messages)
  if (normalized.length) return normalized
  return [
    {
      id: createMessageId("assistant"),
      role: "assistant",
      content: "무엇을 도와드릴까요?",
      isGreeting: true,
      ...(animateGreeting ? { streamId: createMessageId("stream") } : {}),
    },
  ]
}

function normalizeRooms(rawRooms) {
  if (!Array.isArray(rawRooms)) return []
  return rawRooms
    .map((room, index) => {
      const id = typeof room?.id === "string" ? room.id.trim() : ""
      if (!id) return null
      return {
        id,
        name:
          typeof room.name === "string" && room.name.trim()
            ? room.name.trim()
            : `대화 ${index + 1}`,
        ...(room.createdAt ? { createdAt: room.createdAt } : {}),
        ...(room.updatedAt ? { updatedAt: room.updatedAt } : {}),
        pinned: room.pinned === true,
        archived: room.archived === true,
        ...(room.pinnedAt ? { pinnedAt: room.pinnedAt } : {}),
        ...(room.archivedAt ? { archivedAt: room.archivedAt } : {}),
      }
    })
    .filter(Boolean)
}

function isDefaultRoomName(name) {
  return typeof name === "string" && DEFAULT_ROOM_NAME_PATTERN.test(name.trim())
}

function buildInitialState(options) {
  const rooms = normalizeRooms(options.initialRooms)
  const messagesByRoom = {}
  rooms.forEach((room) => {
    messagesByRoom[room.id] = buildInitialMessages(
      options.initialMessagesByRoom?.[room.id] ?? options.initialMessages,
    )
  })
  const activeRoomId = rooms.some((room) => room.id === options.initialActiveRoomId)
    ? options.initialActiveRoomId
    : rooms[0]?.id || null
  return { rooms, messagesByRoom, activeRoomId }
}

function conversationsQueryKey(userKey, archived = false) {
  return ["assistant", "conversations", userKey, archived ? "archived" : "active"]
}

function messagesQueryKey(userKey, roomId) {
  return ["assistant", "conversation-messages", userKey, roomId]
}

function mergeRoomsById(primaryRooms, additionalRooms) {
  const knownIds = new Set(primaryRooms.map((room) => room.id))
  return [
    ...primaryRooms,
    ...additionalRooms.filter((room) => !knownIds.has(room.id)),
  ]
}

function updateConversationPageRoom(previous, room, { include }) {
  const previousRooms = Array.isArray(previous) ? previous : previous?.results
  if (!Array.isArray(previousRooms)) {
    if (!include) return previous
    return { results: [room], nextCursor: "", hasMore: false }
  }
  const remainingRooms = previousRooms.filter((item) => item.id !== room.id)
  const results = include
    ? sortRoomsByRecentQuestion([room, ...remainingRooms])
    : remainingRooms
  return Array.isArray(previous) ? results : { ...previous, results }
}

function updateMessageQueryData(previous, roomId, messages) {
  const previousPage = previous?.page
  return {
    roomId,
    page: {
      results: messages,
      nextCursor: typeof previousPage?.nextCursor === "string" ? previousPage.nextCursor : "",
      hasMore: previousPage?.hasMore === true,
    },
  }
}

function mergeMessagesPreservingPending(serverMessages, localMessages, pendingIds) {
  const hasLocalChanges =
    pendingIds.size > 0 || localMessages.some((message) => message.isStreaming === true)
  return hasLocalChanges ? localMessages : serverMessages
}

function mergeLatestMessagesPreservingOlder(serverMessages, localMessages) {
  if (!serverMessages.length || !localMessages.length) return serverMessages
  const serverMessageIds = new Set(serverMessages.map((message) => message.id))
  const firstSharedIndex = localMessages.findIndex((message) =>
    serverMessageIds.has(message.id),
  )
  if (firstSharedIndex <= 0) return serverMessages
  const olderPrefix = localMessages
    .slice(0, firstSharedIndex)
    .filter((message) => !serverMessageIds.has(message.id))
  return [...olderPrefix, ...serverMessages]
}

function removeConversationIdsFromPage(previous, deletedIds) {
  if (!previous) return previous
  const previousRooms = Array.isArray(previous) ? previous : previous.results
  if (!Array.isArray(previousRooms)) return previous
  const results = previousRooms.filter((room) => !deletedIds.has(room.id))
  return Array.isArray(previous) ? results : { ...previous, results }
}

function enqueueByKey(queue, key, task) {
  const previous = queue.get(key) || Promise.resolve()
  const queued = previous.catch(() => undefined).then(task)
  queue.set(key, queued)
  return queued.finally(() => {
    if (queue.get(key) === queued) queue.delete(key)
  })
}

export function useChatSession(options = {}) {
  const queryClient = useQueryClient()
  const userKey = String(options.userKey || "").trim()
  const persistenceEnabled = Boolean(userKey) && options.persistenceEnabled !== false
  const permissionGroups = normalizeList(options.permissionGroups)
  const ragIndexNames = normalizeList(options.ragIndexNames)
  const mailbox = resolvePrimaryMailbox(permissionGroups)
  const messageSender =
    typeof options.messageSender === "function" ? options.messageSender : sendChatMessage
  const messageContextKey =
    typeof options.messageContextKey === "string" && options.messageContextKey
      ? options.messageContextKey
      : "assistant"
  const userKeyRef = useRef(userKey)
  const titleRequestRoomIdsRef = useRef(new Set())
  const generationControllerRef = useRef(null)
  const generationRunRef = useRef(null)
  const createRoomPromiseRef = useRef(null)
  const sendMessagePromiseRef = useRef(null)
  const resetConversationPromiseRef = useRef(null)
  const retryAssistantSavePromiseRef = useRef(null)
  const removeRoomsPromiseRef = useRef(null)
  const loadMoreRoomsPromiseRef = useRef(null)
  const loadOlderMessagesPromiseByRoomRef = useRef(new Map())
  const roomActionQueueRef = useRef(new Map())
  const feedbackQueueRef = useRef(new Map())
  const sessionEpochRef = useRef(0)
  const isMountedRef = useRef(true)
  const pendingMessageIdsByRoomRef = useRef(new Map())
  const deletedRoomIdsRef = useRef(new Set())
  const roomSearchRequestRef = useRef(0)
  const roomListPageRef = useRef(null)
  const conversationListScopeRef = useRef(`${userKey}:false`)
  const initialRef = useRef(null)
  if (!initialRef.current) initialRef.current = buildInitialState(options)

  const [rooms, setRooms] = useState(initialRef.current.rooms)
  const roomsRef = useRef(initialRef.current.rooms)
  const [messagesByRoom, setMessagesByRoom] = useState(initialRef.current.messagesByRoom)
  const messagesByRoomRef = useRef(initialRef.current.messagesByRoom)
  const [activeRoomId, setActiveRoomId] = useState(initialRef.current.activeRoomId)
  const [errorMessage, setErrorMessage] = useState("")
  const [generationRoomId, setGenerationRoomId] = useState(null)
  const [isPreparingSend, setIsPreparingSend] = useState(false)
  const [isResettingConversation, setIsResettingConversation] = useState(false)
  const [isCreatingRoom, setIsCreatingRoom] = useState(false)
  const [isDeletingRooms, setIsDeletingRooms] = useState(false)
  const [isRetryingAssistantSave, setIsRetryingAssistantSave] = useState(false)
  const [failedRequest, setFailedRequest] = useState(null)
  const [failedAssistantSave, setFailedAssistantSave] = useState(null)
  const [roomListPage, setRoomListPage] = useState({
    items: initialRef.current.rooms,
    search: "",
    nextCursor: "",
    hasMore: false,
    isLoadingMore: false,
    loadedFollowingPage: false,
  })
  const [messagePagesByRoom, setMessagePagesByRoom] = useState({})
  const messagePagesByRoomRef = useRef({})
  const [showArchived, setShowArchived] = useState(false)

  roomListPageRef.current = roomListPage

  const isSessionCurrent = useCallback(
    (sessionEpoch) =>
      isMountedRef.current && sessionEpochRef.current === sessionEpoch,
    [],
  )

  const conversationsQuery = useQuery({
    queryKey: conversationsQueryKey(userKey, showArchived),
    queryFn: ({ signal }) =>
      fetchAssistantConversationPage({ archived: showArchived, signal }),
    enabled: persistenceEnabled,
  })
  const messagesQuery = useQuery({
    queryKey: messagesQueryKey(userKey, activeRoomId),
    queryFn: async ({ signal }) => ({
      roomId: activeRoomId,
      page: await fetchAssistantConversationMessagePage(activeRoomId, { signal }),
    }),
    enabled: persistenceEnabled && Boolean(activeRoomId),
  })
  const chatMutation = useMutation({ mutationFn: (request) => messageSender(request) })
  const createMutation = useMutation({ mutationFn: createAssistantConversation })
  const deleteMutation = useMutation({
    mutationFn: async (roomIds) => {
      const results = await Promise.allSettled(
        roomIds.map((roomId) => deleteAssistantConversation(roomId)),
      )
      return results.reduce(
        (summary, result, index) => {
          const key = result.status === "fulfilled" ? "deletedIds" : "failedIds"
          summary[key].push(roomIds[index])
          return summary
        },
        { deletedIds: [], failedIds: [] },
      )
    },
  })
  const appendMutation = useMutation({
    mutationFn: ({ roomId, messages }) =>
      appendAssistantConversationMessages(roomId, messages),
  })
  const clearMutation = useMutation({ mutationFn: clearAssistantConversationMessages })

  const markPendingMessageIds = (roomId, messages) => {
    const pendingIds = new Set(pendingMessageIdsByRoomRef.current.get(roomId) || [])
    messages.forEach((message) => {
      if (message?.id) pendingIds.add(message.id)
    })
    pendingMessageIdsByRoomRef.current.set(roomId, pendingIds)
  }

  const clearPendingMessageIds = (roomId, messages) => {
    const pendingIds = new Set(pendingMessageIdsByRoomRef.current.get(roomId) || [])
    messages.forEach((message) => {
      if (message?.id) pendingIds.delete(message.id)
    })
    if (pendingIds.size) pendingMessageIdsByRoomRef.current.set(roomId, pendingIds)
    else pendingMessageIdsByRoomRef.current.delete(roomId)
  }

  useEffect(() => {
    messagesByRoomRef.current = messagesByRoom
  }, [messagesByRoom])

  useEffect(() => {
    roomsRef.current = rooms
  }, [rooms])

  useEffect(() => {
    messagePagesByRoomRef.current = messagePagesByRoom
  }, [messagePagesByRoom])

  useEffect(() => {
    isMountedRef.current = true
    const loadOlderMessagePromises = loadOlderMessagesPromiseByRoomRef.current
    const roomActionQueue = roomActionQueueRef.current
    const feedbackQueue = feedbackQueueRef.current
    return () => {
      isMountedRef.current = false
      sessionEpochRef.current += 1
      roomSearchRequestRef.current += 1
      generationControllerRef.current?.abort()
      if (generationRunRef.current) {
        abandonAssistantGeneration(generationRunRef.current)
      }
      generationControllerRef.current = null
      generationRunRef.current = null
      createRoomPromiseRef.current = null
      sendMessagePromiseRef.current = null
      resetConversationPromiseRef.current = null
      retryAssistantSavePromiseRef.current = null
      removeRoomsPromiseRef.current = null
      loadMoreRoomsPromiseRef.current = null
      loadOlderMessagePromises.clear()
      roomActionQueue.clear()
      feedbackQueue.clear()
    }
  }, [])

  useEffect(() => {
    if (userKeyRef.current === userKey) return
    sessionEpochRef.current += 1
    roomSearchRequestRef.current += 1
    userKeyRef.current = userKey
    roomsRef.current = []
    messagesByRoomRef.current = {}
    setRooms([])
    setMessagesByRoom({})
    setActiveRoomId(null)
    setErrorMessage("")
    setGenerationRoomId(null)
    setFailedRequest(null)
    setFailedAssistantSave(null)
    setRoomListPage({
      items: [],
      search: "",
      nextCursor: "",
      hasMore: false,
      isLoadingMore: false,
      loadedFollowingPage: false,
    })
    roomListPageRef.current = {
      items: [],
      search: "",
      nextCursor: "",
      hasMore: false,
      isLoadingMore: false,
      loadedFollowingPage: false,
    }
    setMessagePagesByRoom({})
    messagePagesByRoomRef.current = {}
    setShowArchived(false)
    generationControllerRef.current?.abort()
    if (generationRunRef.current) {
      abandonAssistantGeneration(generationRunRef.current)
    }
    generationControllerRef.current = null
    generationRunRef.current = null
    createRoomPromiseRef.current = null
    sendMessagePromiseRef.current = null
    resetConversationPromiseRef.current = null
    retryAssistantSavePromiseRef.current = null
    removeRoomsPromiseRef.current = null
    loadMoreRoomsPromiseRef.current = null
    loadOlderMessagesPromiseByRoomRef.current.clear()
    roomActionQueueRef.current.clear()
    feedbackQueueRef.current.clear()
    setIsPreparingSend(false)
    setIsResettingConversation(false)
    setIsCreatingRoom(false)
    setIsDeletingRooms(false)
    setIsRetryingAssistantSave(false)
    pendingMessageIdsByRoomRef.current.clear()
    deletedRoomIdsRef.current.clear()
    titleRequestRoomIdsRef.current.clear()
  }, [userKey])

  useEffect(() => {
    const handlePageHide = () => {
      if (!generationRunRef.current) return
      abandonAssistantGeneration(generationRunRef.current)
      generationRunRef.current = null
    }
    window.addEventListener("pagehide", handlePageHide)
    return () => window.removeEventListener("pagehide", handlePageHide)
  }, [])

  useEffect(() => {
    const rawPage = conversationsQuery.data
    const rawRooms = Array.isArray(rawPage) ? rawPage : rawPage?.results
    if (!persistenceEnabled || !Array.isArray(rawRooms)) return
    const serverRooms = normalizeRooms(rawRooms).filter(
      (room) => !deletedRoomIdsRef.current.has(room.id),
    )
    if (rawRooms.some((room) => deletedRoomIdsRef.current.has(room?.id))) {
      queryClient.setQueryData(
        conversationsQueryKey(userKey, showArchived),
        (previous) =>
          removeConversationIdsFromPage(previous, deletedRoomIdsRef.current),
      )
    }
    const scopeKey = `${userKey}:${showArchived}`
    const scopeChanged = conversationListScopeRef.current !== scopeKey
    const previousPage = roomListPageRef.current
    conversationListScopeRef.current = scopeKey
    if (!scopeChanged && previousPage?.search) {
      setRooms((previous) => mergeRoomsById(serverRooms, previous))
      return
    }
    const hasLoadedFollowingPage =
      !scopeChanged &&
      previousPage?.search === "" &&
      previousPage?.loadedFollowingPage === true
    const visibleRooms = hasLoadedFollowingPage
      ? mergeRoomsById(serverRooms, previousPage.items)
      : serverRooms
    setRooms(visibleRooms)
    setRoomListPage({
      items: visibleRooms,
      search: "",
      nextCursor: hasLoadedFollowingPage
        ? previousPage.nextCursor
        : typeof rawPage?.nextCursor === "string"
          ? rawPage.nextCursor
          : "",
      hasMore: hasLoadedFollowingPage ? previousPage.hasMore : rawPage?.hasMore === true,
      isLoadingMore: false,
      loadedFollowingPage: hasLoadedFollowingPage,
    })
    setMessagesByRoom((previous) =>
      Object.fromEntries(
        Object.entries(previous).filter(([roomId]) =>
          visibleRooms.some((room) => room.id === roomId),
        ),
      ),
    )
    setActiveRoomId((previous) => {
      const nextRoomId =
        (visibleRooms.some((room) => room.id === previous) && previous) ||
        visibleRooms[0]?.id ||
        null
      return nextRoomId
    })
  }, [conversationsQuery.data, persistenceEnabled, queryClient, showArchived, userKey])

  useEffect(() => {
    const loadedRoomId = messagesQuery.data?.roomId
    const loadedPage = messagesQuery.data?.page
    const loadedMessages = Array.isArray(loadedPage) ? loadedPage : loadedPage?.results
    if (!persistenceEnabled || !loadedRoomId || !Array.isArray(loadedMessages)) return
    setMessagesByRoom((previous) => {
      const currentMessages = previous[loadedRoomId]
      const hasStreamingGreeting =
        loadedMessages.length === 0 &&
        currentMessages?.length === 1 &&
        Boolean(currentMessages[0]?.streamId)
      const serverMessages = buildInitialMessages(loadedMessages)
      const pendingIds = new Set(
        pendingMessageIdsByRoomRef.current.get(loadedRoomId) || [],
      )
      const hasLoadedOlderPage =
        messagePagesByRoomRef.current[loadedRoomId]?.loadedOlderPage === true
      const mergedServerMessages = hasLoadedOlderPage
        ? mergeLatestMessagesPreservingOlder(serverMessages, currentMessages || [])
        : serverMessages
      const nextRoomMessages = hasStreamingGreeting
        ? currentMessages
        : mergeMessagesPreservingPending(
            mergedServerMessages,
            currentMessages || [],
            pendingIds,
          )
      const nextMessagesByRoom = {
        ...previous,
        [loadedRoomId]: nextRoomMessages,
      }
      messagesByRoomRef.current = nextMessagesByRoom
      return nextMessagesByRoom
    })
    setMessagePagesByRoom((previous) => {
      const previousPage = previous[loadedRoomId]
      const hasLoadedOlderPage = previousPage?.loadedOlderPage === true
      const nextPage = {
        nextCursor: hasLoadedOlderPage
          ? previousPage.nextCursor
          : typeof loadedPage?.nextCursor === "string"
            ? loadedPage.nextCursor
            : "",
        hasMore: hasLoadedOlderPage
          ? previousPage.hasMore
          : loadedPage?.hasMore === true,
        isLoadingOlder: false,
        loadedOlderPage: hasLoadedOlderPage,
      }
      messagePagesByRoomRef.current = {
        ...messagePagesByRoomRef.current,
        [loadedRoomId]: nextPage,
      }
      return { ...previous, [loadedRoomId]: nextPage }
    })
  }, [messagesQuery.data, persistenceEnabled])

  useEffect(() => {
    const queryError = conversationsQuery.error || messagesQuery.error
    if (queryError) setErrorMessage(queryError.message || "대화 이력을 불러오지 못했어요.")
  }, [conversationsQuery.error, messagesQuery.error])

  const syncConversationRoomCaches = useCallback(
    (room) => {
      if (!persistenceEnabled) return
      const normalizedRoom = normalizeRooms([room])[0]
      if (!normalizedRoom) return
      queryClient.setQueryData(
        conversationsQueryKey(userKey, false),
        (previous) =>
          updateConversationPageRoom(previous, normalizedRoom, {
            include: !normalizedRoom.archived,
          }),
      )
      queryClient.setQueryData(
        conversationsQueryKey(userKey, true),
        (previous) =>
          updateConversationPageRoom(previous, normalizedRoom, {
            include: normalizedRoom.archived,
          }),
      )
    },
    [persistenceEnabled, queryClient, userKey],
  )

  const replaceRoom = useCallback(
    (room) => {
      const normalizedRoom = normalizeRooms([room])[0]
      if (!normalizedRoom) return
      const update = (previous = []) =>
        previous.map((item) =>
          item.id === normalizedRoom.id ? normalizedRoom : item,
        )
      const nextRooms = update(roomsRef.current)
      roomsRef.current = nextRooms
      setRooms(nextRooms)
      setRoomListPage((previous) => ({
        ...previous,
        items: update(previous.items),
      }))
      syncConversationRoomCaches(normalizedRoom)
    },
    [syncConversationRoomCaches],
  )

  const touchRoom = useCallback(
    (roomId) => {
      const updatedAt = new Date().toISOString()
      const room = roomsRef.current.find((item) => item.id === roomId)
      if (!room) return
      const touchedRoom = { ...room, updatedAt }
      const update = (previous = []) =>
        previous.map((item) => (item.id === roomId ? touchedRoom : item))
      const nextRooms = update(roomsRef.current)
      roomsRef.current = nextRooms
      setRooms(nextRooms)
      setRoomListPage((previous) => ({
        ...previous,
        items: update(previous.items),
      }))
      syncConversationRoomCaches(touchedRoom)
    },
    [syncConversationRoomCaches],
  )

  const requestGeneratedRoomTitle = useCallback(
    async (roomId) => {
      if (!persistenceEnabled || titleRequestRoomIdsRef.current.has(roomId)) return
      const sessionEpoch = sessionEpochRef.current
      const room = roomsRef.current.find((item) => item.id === roomId)
      if (!room || !isDefaultRoomName(room.name)) return

      titleRequestRoomIdsRef.current.add(roomId)
      try {
        const titledRoom = normalizeRooms([
          await generateAssistantConversationTitle(roomId),
        ])[0]
        if (!titledRoom || !isSessionCurrent(sessionEpoch)) return
        replaceRoom(titledRoom)
      } catch {
        // 제목 생성 실패는 채팅 답변과 메시지 저장 성공에 영향을 주지 않습니다.
      } finally {
        titleRequestRoomIdsRef.current.delete(roomId)
      }
    },
    [isSessionCurrent, persistenceEnabled, replaceRoom],
  )

  const createRoom = useCallback(
    async (label) => {
      if (createRoomPromiseRef.current) return createRoomPromiseRef.current
      if (resetConversationPromiseRef.current) return null
      if (persistenceEnabled && conversationsQuery.isLoading) return null
      const sessionEpoch = sessionEpochRef.current
      setIsCreatingRoom(true)
      const createPromise = (async () => {
        if (persistenceEnabled) {
          await queryClient.cancelQueries({
            queryKey: ["assistant", "conversations", userKey],
          })
          if (!isSessionCurrent(sessionEpoch)) return null
        }
        if (showArchived) setShowArchived(false)
        const name = typeof label === "string" && label.trim()
          ? label.trim()
          : `새 대화 ${roomsRef.current.length + 1}`
        const created = persistenceEnabled
          ? await createMutation.mutateAsync({ name })
          : { id: generateLocalRoomId(), name, updatedAt: new Date().toISOString() }
        if (!isSessionCurrent(sessionEpoch)) return null
        const room = normalizeRooms([created])[0]
        if (!room) throw new Error("생성된 대화방 정보가 올바르지 않습니다.")
        const nextRooms = [
          room,
          ...roomsRef.current.filter((item) => item.id !== room.id),
        ]
        roomsRef.current = nextRooms
        setRooms(nextRooms)
        setRoomListPage((previous) => ({
          ...previous,
          items: previous.search
            ? previous.items
            : [room, ...previous.items.filter((item) => item.id !== room.id)],
        }))
        const nextMessagesByRoom = {
          ...messagesByRoomRef.current,
          [room.id]: buildInitialMessages([], { animateGreeting: true }),
        }
        messagesByRoomRef.current = nextMessagesByRoom
        setMessagesByRoom(nextMessagesByRoom)
        setActiveRoomId(room.id)
        syncConversationRoomCaches(room)
        queryClient.setQueryData(messagesQueryKey(userKey, room.id), (previous) =>
          updateMessageQueryData(previous, room.id, []),
        )
        setErrorMessage("")
        return room.id
      })()
      createRoomPromiseRef.current = createPromise
      try {
        return await createPromise
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화방을 만들지 못했어요.")
        }
        return null
      } finally {
        if (createRoomPromiseRef.current === createPromise) {
          createRoomPromiseRef.current = null
          if (isSessionCurrent(sessionEpoch)) setIsCreatingRoom(false)
        }
      }
    },
    [
      conversationsQuery.isLoading,
      createMutation,
      isSessionCurrent,
      persistenceEnabled,
      queryClient,
      syncConversationRoomCaches,
      userKey,
      showArchived,
    ],
  )

  const selectRoom = useCallback(
    (roomId) => {
      if (!rooms.some((room) => room.id === roomId)) return
      setActiveRoomId(roomId)
      setErrorMessage("")
    },
    [rooms],
  )

  const searchRooms = useCallback(
    async (search = "") => {
      if (!persistenceEnabled) {
        const normalizedSearch = String(search || "").trim().toLowerCase()
        setRoomListPage((previous) => ({
          ...previous,
          search: normalizedSearch,
          items: roomsRef.current.filter((room) =>
            room.name.toLowerCase().includes(normalizedSearch),
          ),
          hasMore: false,
          nextCursor: "",
        }))
        return
      }
      const requestId = roomSearchRequestRef.current + 1
      const sessionEpoch = sessionEpochRef.current
      roomSearchRequestRef.current = requestId
      const normalizedSearch = String(search || "").trim()
      const loadingPage = {
        ...roomListPageRef.current,
        search: normalizedSearch,
        isLoadingMore: true,
      }
      roomListPageRef.current = loadingPage
      setRoomListPage(loadingPage)
      try {
        const page = await fetchAssistantConversationPage({
          search: normalizedSearch,
          archived: showArchived,
        })
        if (
          requestId !== roomSearchRequestRef.current ||
          !isSessionCurrent(sessionEpoch)
        ) return
        const pageRooms = normalizeRooms(page.results).filter(
          (room) => !deletedRoomIdsRef.current.has(room.id),
        )
        setRooms((previous) => [
          ...previous,
          ...pageRooms.filter((room) => !previous.some((item) => item.id === room.id)),
        ])
        const nextPage = {
          items: pageRooms,
          search: normalizedSearch,
          nextCursor: page.nextCursor,
          hasMore: page.hasMore,
          isLoadingMore: false,
          loadedFollowingPage: false,
        }
        roomListPageRef.current = nextPage
        setRoomListPage(nextPage)
      } catch (error) {
        if (
          requestId !== roomSearchRequestRef.current ||
          !isSessionCurrent(sessionEpoch)
        ) return
        const nextPage = { ...roomListPageRef.current, isLoadingMore: false }
        roomListPageRef.current = nextPage
        setRoomListPage(nextPage)
        setErrorMessage(error?.message || "대화방을 검색하지 못했어요.")
      }
    },
    [isSessionCurrent, persistenceEnabled, showArchived],
  )

  const loadMoreRooms = useCallback(async () => {
    if (loadMoreRoomsPromiseRef.current) return loadMoreRoomsPromiseRef.current
    const pageState = roomListPageRef.current
    if (
      !persistenceEnabled ||
      !pageState?.hasMore ||
      !pageState.nextCursor ||
      pageState.isLoadingMore
    ) {
      return { ok: false, addedCount: 0 }
    }
    const sessionEpoch = sessionEpochRef.current
    const searchRequestId = roomSearchRequestRef.current
    roomListPageRef.current = { ...pageState, isLoadingMore: true }
    setRoomListPage(roomListPageRef.current)
    const loadPromise = (async () => {
      try {
        const page = await fetchAssistantConversationPage({
          search: pageState.search,
          cursor: pageState.nextCursor,
          archived: showArchived,
        })
        if (
          !isSessionCurrent(sessionEpoch) ||
          searchRequestId !== roomSearchRequestRef.current
        ) return { ok: false, addedCount: 0 }
        const pageRooms = normalizeRooms(page.results).filter(
          (room) => !deletedRoomIdsRef.current.has(room.id),
        )
        setRooms((previous) => [
          ...previous,
          ...pageRooms.filter((room) => !previous.some((item) => item.id === room.id)),
        ])
        const previousPage = roomListPageRef.current
        const addedRooms = pageRooms.filter(
          (room) => !previousPage.items.some((item) => item.id === room.id),
        )
        const nextPage = {
          ...previousPage,
          items: [...previousPage.items, ...addedRooms],
          nextCursor: page.nextCursor,
          hasMore: page.hasMore,
          isLoadingMore: false,
          loadedFollowingPage: true,
        }
        roomListPageRef.current = nextPage
        setRoomListPage(nextPage)
        return { ok: true, addedCount: addedRooms.length }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          const nextPage = { ...roomListPageRef.current, isLoadingMore: false }
          roomListPageRef.current = nextPage
          setRoomListPage(nextPage)
          setErrorMessage(error?.message || "대화방을 더 불러오지 못했어요.")
        }
        return { ok: false, addedCount: 0 }
      }
    })()
    loadMoreRoomsPromiseRef.current = loadPromise
    try {
      return await loadPromise
    } finally {
      if (loadMoreRoomsPromiseRef.current === loadPromise) {
        loadMoreRoomsPromiseRef.current = null
      }
    }
  }, [isSessionCurrent, persistenceEnabled, showArchived])

  const loadOlderMessages = useCallback(
    async (roomId = activeRoomId) => {
      const pendingPromise = loadOlderMessagesPromiseByRoomRef.current.get(roomId)
      if (pendingPromise) return pendingPromise
      const pageState = messagePagesByRoomRef.current[roomId]
      if (
        !persistenceEnabled ||
        !roomId ||
        !pageState?.hasMore ||
        !pageState.nextCursor ||
        pageState.isLoadingOlder
      ) {
        return { ok: false, addedCount: 0 }
      }
      const sessionEpoch = sessionEpochRef.current
      messagePagesByRoomRef.current = {
        ...messagePagesByRoomRef.current,
        [roomId]: { ...pageState, isLoadingOlder: true },
      }
      setMessagePagesByRoom((previous) => ({
        ...previous,
        [roomId]: { ...previous[roomId], isLoadingOlder: true },
      }))
      const loadPromise = (async () => {
        try {
          const page = await fetchAssistantConversationMessagePage(roomId, {
            before: pageState.nextCursor,
          })
          if (!isSessionCurrent(sessionEpoch)) return { ok: false, addedCount: 0 }
          const olderMessages = normalizeMessages(page.results)
          const currentRoomMessages = messagesByRoomRef.current[roomId] || []
          const addedMessages = olderMessages.filter(
            (message) => !currentRoomMessages.some((item) => item.id === message.id),
          )
          const mergedRoomMessages = [...addedMessages, ...currentRoomMessages]
          if (addedMessages.length) {
            const nextMessagesByRoom = {
              ...messagesByRoomRef.current,
              [roomId]: mergedRoomMessages,
            }
            messagesByRoomRef.current = nextMessagesByRoom
            setMessagesByRoom(nextMessagesByRoom)
          }
          const nextPageState = {
            nextCursor: page.nextCursor,
            hasMore: page.hasMore,
            isLoadingOlder: false,
            loadedOlderPage: true,
          }
          setMessagePagesByRoom((previous) => ({
            ...previous,
            [roomId]: nextPageState,
          }))
          messagePagesByRoomRef.current = {
            ...messagePagesByRoomRef.current,
            [roomId]: nextPageState,
          }
          queryClient.setQueryData(messagesQueryKey(userKey, roomId), () => ({
            roomId,
            page: {
              results: mergedRoomMessages,
              nextCursor: page.nextCursor,
              hasMore: page.hasMore,
            },
          }))
          return { ok: true, addedCount: addedMessages.length }
        } catch (error) {
          if (isSessionCurrent(sessionEpoch)) {
            const nextPageState = {
              ...messagePagesByRoomRef.current[roomId],
              isLoadingOlder: false,
            }
            messagePagesByRoomRef.current = {
              ...messagePagesByRoomRef.current,
              [roomId]: nextPageState,
            }
            setMessagePagesByRoom((previous) => ({
              ...previous,
              [roomId]: nextPageState,
            }))
            setErrorMessage(error?.message || "이전 메시지를 불러오지 못했어요.")
          }
          return { ok: false, addedCount: 0 }
        }
      })()
      loadOlderMessagesPromiseByRoomRef.current.set(roomId, loadPromise)
      try {
        return await loadPromise
      } finally {
        if (loadOlderMessagesPromiseByRoomRef.current.get(roomId) === loadPromise) {
          loadOlderMessagesPromiseByRoomRef.current.delete(roomId)
        }
      }
    },
    [
      activeRoomId,
      isSessionCurrent,
      persistenceEnabled,
      queryClient,
      userKey,
    ],
  )

  const getOrCreateActiveRoomId = async (preferredRoomId) => {
    if (preferredRoomId && rooms.some((room) => room.id === preferredRoomId)) {
      return preferredRoomId
    }
    if (activeRoomId && rooms.some((room) => room.id === activeRoomId)) {
      return activeRoomId
    }
    if (rooms[0]?.id) return rooms[0].id
    return createRoom()
  }

  const resetConversation = async (roomId = activeRoomId) => {
    if (resetConversationPromiseRef.current) {
      return resetConversationPromiseRef.current
    }
    const targetRoomId = rooms.some((room) => room.id === roomId) ? roomId : null
    if (!targetRoomId) return { ok: false }
    if (
      sendMessagePromiseRef.current ||
      createRoomPromiseRef.current ||
      generationControllerRef.current
    ) {
      setErrorMessage("답변 생성이 끝난 뒤 대화를 초기화해주세요.")
      return { ok: false }
    }
    const sessionEpoch = sessionEpochRef.current
    setIsResettingConversation(true)
    const resetPromise = (async () => {
      try {
        if (persistenceEnabled) await clearMutation.mutateAsync(targetRoomId)
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        pendingMessageIdsByRoomRef.current.delete(targetRoomId)
        const nextRoomMessages = buildInitialMessages()
        const nextMessagesByRoom = {
          ...messagesByRoomRef.current,
          [targetRoomId]: nextRoomMessages,
        }
        messagesByRoomRef.current = nextMessagesByRoom
        setMessagesByRoom(nextMessagesByRoom)
        const nextPageState = {
          nextCursor: "",
          hasMore: false,
          isLoadingOlder: false,
          loadedOlderPage: false,
        }
        messagePagesByRoomRef.current = {
          ...messagePagesByRoomRef.current,
          [targetRoomId]: nextPageState,
        }
        setMessagePagesByRoom((previous) => ({
          ...previous,
          [targetRoomId]: nextPageState,
        }))
        queryClient.setQueryData(messagesQueryKey(userKey, targetRoomId), (previous) =>
          updateMessageQueryData(previous, targetRoomId, []),
        )
        touchRoom(targetRoomId)
        setErrorMessage("")
        chatMutation.reset()
        return { ok: true }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화를 초기화하지 못했어요.")
        }
        return { ok: false }
      }
    })()
    resetConversationPromiseRef.current = resetPromise
    try {
      return await resetPromise
    } finally {
      if (resetConversationPromiseRef.current === resetPromise) {
        resetConversationPromiseRef.current = null
        setIsResettingConversation(false)
      }
    }
  }

  const isHistoryLoading =
    persistenceEnabled &&
    Boolean(activeRoomId) &&
    messagesQuery.isLoading &&
    !messagesByRoom[activeRoomId]
  const hasActiveGeneration = Boolean(generationRoomId)
  const isSending =
    isPreparingSend ||
    isResettingConversation ||
    isRetryingAssistantSave ||
    hasActiveGeneration ||
    isCreatingRoom ||
    (persistenceEnabled && conversationsQuery.isLoading) ||
    isHistoryLoading
  const isGenerating =
    hasActiveGeneration && generationRoomId === activeRoomId
  const isRoomListBusy =
    isCreatingRoom ||
    isResettingConversation ||
    isDeletingRooms ||
    (persistenceEnabled && conversationsQuery.isLoading)

  const executeSendMessage = async (input, options = {}) => {
    const sessionEpoch = sessionEpochRef.current
    const text = typeof input === "string" ? input.trim() : ""
    if (!text) {
      setErrorMessage("보낼 메시지를 입력해주세요.")
      return { ok: false, accepted: false }
    }
    if (text.length > MAX_ASSISTANT_MESSAGE_CHARS) {
      setErrorMessage(
        `메시지는 최대 ${MAX_ASSISTANT_MESSAGE_CHARS.toLocaleString()}자까지 보낼 수 있어요.`,
      )
      return { ok: false, accepted: false }
    }
    if (
      failedAssistantSave &&
      failedAssistantSave.contextKey === messageContextKey
    ) {
      setErrorMessage("먼저 표시된 답변 저장을 다시 시도해주세요.")
      return { ok: false, accepted: false }
    }
    if (resetConversationPromiseRef.current) {
      setErrorMessage("대화 초기화가 끝난 뒤 메시지를 보내주세요.")
      return { ok: false, accepted: false }
    }
    if (generationControllerRef.current || isHistoryLoading) {
      if (generationControllerRef.current) {
        setErrorMessage("다른 대화방에서 답변을 생성하고 있어요.")
      }
      return { ok: false, accepted: false }
    }

    const roomId = await getOrCreateActiveRoomId(options.roomId)
    if (!roomId || !isSessionCurrent(sessionEpoch)) {
      return { ok: false, accepted: false }
    }
    if (persistenceEnabled) {
      await queryClient.cancelQueries({
        queryKey: messagesQueryKey(userKey, roomId),
        exact: true,
      })
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
    }
    const requestContextKey = messageContextKey
    const originalMessages = messagesByRoomRef.current[roomId] ?? buildInitialMessages()
    const currentMessages = Array.isArray(options.baseMessages)
      ? options.baseMessages
      : originalMessages
    const reusableUserMessage = options.reuseLastUserMessage
      ? [...currentMessages]
          .reverse()
          .find(
            (message) =>
              message.role === "user" &&
              message.content === text &&
              message.contextKey === requestContextKey,
          )
      : null
    const lastParentMessage = [...currentMessages]
      .reverse()
      .find((message) => !message.isGreeting)
    const userMessage =
      options.preparedUserMessage || reusableUserMessage || {
        id: createMessageId("user"),
        role: "user",
        content: text,
        contextKey: requestContextKey,
        createdAt: new Date().toISOString(),
        ...(lastParentMessage ? { parentId: lastParentMessage.id } : {}),
      }
    const nextMessages = reusableUserMessage && !options.preparedUserMessage
      ? currentMessages
      : [...currentMessages, userMessage]
    markPendingMessageIds(roomId, [userMessage])
    const historyForRequest = nextMessages
      .filter((message) => isSameChatMemory(message.contextKey, requestContextKey))
      .slice(-MAX_MODEL_HISTORY)
    let generation = null
    if (persistenceEnabled) {
      try {
        generation = await acquireAssistantGeneration({
          conversationId: roomId,
          clientRequestId: `request-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          contextKey: requestContextKey,
        })
        if (!generation || !["queued", "streaming"].includes(generation.status)) {
          throw new Error("생성 요청이 이미 종료되었습니다. 다시 시도해주세요.")
        }
        generationRunRef.current = generation?.id || null
        if (!isSessionCurrent(sessionEpoch)) {
          abandonAssistantGeneration(generation?.id)
          if (generationRunRef.current === generation?.id) {
            generationRunRef.current = null
          }
          return { ok: false, accepted: false }
        }
      } catch (error) {
        if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
        clearPendingMessageIds(roomId, [userMessage])
        setErrorMessage(error?.message || "다른 대화에서 답변을 생성하고 있어요.")
        return { ok: false, accepted: false }
      }
    }

    messagesByRoomRef.current = {
      ...messagesByRoomRef.current,
      [roomId]: nextMessages,
    }
    setMessagesByRoom((previous) => ({ ...previous, [roomId]: nextMessages }))
    queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
      updateMessageQueryData(previous, roomId, nextMessages),
    )
    touchRoom(roomId)
    setErrorMessage("")

    if (persistenceEnabled && (!reusableUserMessage || options.preparedUserMessage)) {
      try {
        await appendMutation.mutateAsync({ roomId, messages: [userMessage] })
        if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
      } catch (error) {
        if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
        clearPendingMessageIds(roomId, [userMessage])
        messagesByRoomRef.current = {
          ...messagesByRoomRef.current,
          [roomId]: originalMessages,
        }
        setMessagesByRoom((previous) => ({
          ...previous,
          [roomId]: originalMessages,
        }))
        queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
          updateMessageQueryData(previous, roomId, originalMessages),
        )
        if (generation?.id) {
          await finalizeAssistantGeneration(generation.id, "failed", "message_save_failed").catch(
            () => {},
          )
          if (generationRunRef.current === generation.id) {
            generationRunRef.current = null
          }
        }
        setErrorMessage(error?.message || "사용자 메시지를 저장하지 못했어요.")
        return { ok: false, accepted: false }
      }
    }

    const controller = new AbortController()
    const streamingMessageId = createMessageId("assistant")
    const streamingMessage = { id: streamingMessageId }
    let streamedContent = ""
    let isStreamFinished = false
    let streamFramePending = false
    let cancelStreamFrame = () => {}
    markPendingMessageIds(roomId, [streamingMessage])
    generationControllerRef.current = controller
    setGenerationRoomId(roomId)
    setFailedRequest(null)

    const flushStreamDelta = () => {
      streamFramePending = false
      cancelStreamFrame = () => {}
      if (isStreamFinished || !isSessionCurrent(sessionEpoch)) return
      setMessagesByRoom((previous) => {
        const roomMessages = previous[roomId] || nextMessages
        const existingIndex = roomMessages.findIndex(
          (message) => message.id === streamingMessageId,
        )
        const streamingMessage = {
          id: streamingMessageId,
          role: "assistant",
          content: streamedContent,
          contextKey: requestContextKey,
          isStreaming: true,
          parentId: userMessage.id,
          ...(generation?.id ? { generationId: generation.id } : {}),
          ...(mailbox ? { userSdwtProd: mailbox } : {}),
          createdAt: new Date().toISOString(),
        }
        const updatedMessages = [...roomMessages]
        if (existingIndex >= 0) updatedMessages[existingIndex] = streamingMessage
        else updatedMessages.push(streamingMessage)
        const nextRoomMessages = updatedMessages
        messagesByRoomRef.current = {
          ...messagesByRoomRef.current,
          [roomId]: nextRoomMessages,
        }
        return { ...previous, [roomId]: nextRoomMessages }
      })
    }

    const appendStreamDelta = (delta) => {
      if (typeof delta !== "string" || !delta || isStreamFinished) return
      streamedContent += delta
      if (streamFramePending) return
      streamFramePending = true
      if (typeof window !== "undefined" && window.requestAnimationFrame) {
        const frameId = window.requestAnimationFrame(flushStreamDelta)
        cancelStreamFrame = () => window.cancelAnimationFrame(frameId)
      } else {
        const timeoutId = setTimeout(flushStreamDelta, 16)
        cancelStreamFrame = () => clearTimeout(timeoutId)
      }
    }

    try {
      const result = await chatMutation.mutateAsync({
        prompt: text,
        history: historyForRequest.map((message) => ({
          role: message.role,
          content:
            message.id === userMessage.id
              ? message.content
              : formatChatHistoryContent(
                  message.content,
                  message.contextKey,
                  requestContextKey,
                ),
        })),
        roomId,
        permissionGroups,
        ragIndexNames,
        contextKey: requestContextKey,
        signal: controller.signal,
        onDelta: appendStreamDelta,
      })
      isStreamFinished = true
      cancelStreamFrame()
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }

      const segments = Array.isArray(result?.segments) ? result.segments : []
      const assistantMessages = segments
        .map((segment, index) => {
          const content = typeof segment?.reply === "string" ? segment.reply.trim() : ""
          if (!content) return null
          return {
            id: createMessageId("assistant"),
            role: "assistant",
            content,
            sources: normalizeChatSources(segment.sources),
            contextKey: requestContextKey,
            parentId: index === 0 ? userMessage.id : undefined,
            ...(generation?.id ? { generationId: generation.id } : {}),
            ...(mailbox ? { userSdwtProd: mailbox } : {}),
            createdAt: new Date().toISOString(),
          }
        })
        .filter(Boolean)
      if (!assistantMessages.length) {
        assistantMessages.push({
          id: streamedContent ? streamingMessageId : createMessageId("assistant"),
          role: "assistant",
          content:
            typeof result?.reply === "string" && result.reply.trim()
              ? result.reply.trim()
              : "답변을 불러오지 못했어요. 잠시 후 다시 시도해주세요.",
          sources: normalizeChatSources(result?.sources),
          contextKey: requestContextKey,
          parentId: userMessage.id,
          ...(generation?.id ? { generationId: generation.id } : {}),
          ...(result?.contextSnapshot
            ? { contextSnapshot: result.contextSnapshot }
            : {}),
          ...(mailbox ? { userSdwtProd: mailbox } : {}),
          createdAt: new Date().toISOString(),
        })
      }

      assistantMessages.forEach((message, index) => {
        if (index > 0) message.parentId = assistantMessages[index - 1].id
        if (index === assistantMessages.length - 1 && result?.contextSnapshot) {
          message.contextSnapshot = result.contextSnapshot
        }
      })
      const normalizedAssistantMessages = assistantMessages.map(
        normalizeGeneratedAssistantMessage,
      )
      clearPendingMessageIds(roomId, [streamingMessage])
      markPendingMessageIds(roomId, normalizedAssistantMessages)

      const latestMessages = messagesByRoomRef.current[roomId] || nextMessages
      const finalMessages = [
        ...latestMessages.filter((message) => message.id !== streamingMessageId),
        ...normalizedAssistantMessages.map((message) => ({
          ...message,
          isStreaming: false,
        })),
      ]
      messagesByRoomRef.current = {
        ...messagesByRoomRef.current,
        [roomId]: finalMessages,
      }
      setMessagesByRoom((previous) => ({ ...previous, [roomId]: finalMessages }))
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
        updateMessageQueryData(previous, roomId, finalMessages),
      )
      touchRoom(roomId)
      let assistantMessagesPersisted = true
      if (persistenceEnabled) {
        try {
          await appendMutation.mutateAsync({
            roomId,
            messages: normalizedAssistantMessages,
          })
          if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
          setFailedAssistantSave((previous) =>
            previous?.contextKey === requestContextKey ? null : previous,
          )
          clearPendingMessageIds(roomId, [userMessage, ...normalizedAssistantMessages])
          void requestGeneratedRoomTitle(roomId)
          void refreshAssistantConversationSummary(roomId, requestContextKey).catch(() => {})
          void queryClient.invalidateQueries({
            queryKey: messagesQueryKey(userKey, roomId),
            exact: true,
          })
        } catch (error) {
          if (!isSessionCurrent(sessionEpoch)) {
            return { ok: false, accepted: false }
          }
          assistantMessagesPersisted = false
          clearPendingMessageIds(roomId, [userMessage])
          setFailedAssistantSave({
            roomId,
            messages: normalizedAssistantMessages,
            contextKey: requestContextKey,
          })
          setErrorMessage(
            error?.message || "답변은 표시했지만 대화 이력을 저장하지 못했어요.",
          )
        }
      } else {
        clearPendingMessageIds(roomId, [userMessage, ...normalizedAssistantMessages])
      }
      if (generation?.id) {
        if (assistantMessagesPersisted) {
          await finalizeAssistantGeneration(generation.id, "completed").catch(() => {})
        } else {
          await finalizeAssistantGeneration(
            generation.id,
            "failed",
            "message_save_failed",
          ).catch(() => {})
        }
        if (generationRunRef.current === generation.id) {
          generationRunRef.current = null
        }
      }
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
      setFailedRequest(null)
      return { ok: true, accepted: true, roomId }
    } catch (error) {
      isStreamFinished = true
      cancelStreamFrame()
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
      const isCancelled = error?.name === "AbortError"
      clearPendingMessageIds(roomId, [userMessage, streamingMessage])
      const latestMessages = messagesByRoomRef.current[roomId] || nextMessages
      const messagesWithoutStream = latestMessages.filter(
        (message) => message.id !== streamingMessageId,
      )
      messagesByRoomRef.current = {
        ...messagesByRoomRef.current,
        [roomId]: messagesWithoutStream,
      }
      setMessagesByRoom((previous) => ({
        ...previous,
        [roomId]: messagesWithoutStream,
      }))
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
        updateMessageQueryData(previous, roomId, messagesWithoutStream),
      )
      if (persistenceEnabled) {
        void queryClient.invalidateQueries({
          queryKey: messagesQueryKey(userKey, roomId),
          exact: true,
        })
      }
      if (isCancelled) {
        if (generation?.id) {
          await finalizeAssistantGeneration(generation.id, "stopped").catch(() => {})
          if (generationRunRef.current === generation.id) {
            generationRunRef.current = null
          }
        }
        setErrorMessage("")
        return { ok: true, accepted: true, cancelled: true, roomId }
      }
      setFailedRequest({ roomId, text, contextKey: requestContextKey })
      if (generation?.id) {
        await finalizeAssistantGeneration(generation.id, "failed", "request_failed").catch(
          () => {},
        )
        if (generationRunRef.current === generation.id) {
          generationRunRef.current = null
        }
      }
      setErrorMessage(error?.message || "메시지를 전송하지 못했어요.")
      return { ok: false, accepted: true, roomId }
    } finally {
      isStreamFinished = true
      cancelStreamFrame()
      if (generationControllerRef.current === controller) {
        generationControllerRef.current = null
        setGenerationRoomId(null)
      }
    }
  }

  const sendMessage = async (input, options = {}) => {
    if (sendMessagePromiseRef.current) {
      setErrorMessage(
        generationControllerRef.current
          ? "다른 대화방에서 답변을 생성하고 있어요."
          : "이미 메시지를 전송하고 있어요.",
      )
      return { ok: false, accepted: false }
    }
    setIsPreparingSend(true)
    const sendPromise = executeSendMessage(input, options)
    sendMessagePromiseRef.current = sendPromise
    try {
      return await sendPromise
    } finally {
      if (sendMessagePromiseRef.current === sendPromise) {
        sendMessagePromiseRef.current = null
        setIsPreparingSend(false)
      }
    }
  }

  const stopGenerating = () => {
    generationControllerRef.current?.abort()
  }

  const retryAssistantSave = async () => {
    if (retryAssistantSavePromiseRef.current) {
      return retryAssistantSavePromiseRef.current
    }
    if (
      !persistenceEnabled ||
      !failedAssistantSave ||
      failedAssistantSave.contextKey !== messageContextKey ||
      sendMessagePromiseRef.current
    ) {
      return { ok: false }
    }
    const sessionEpoch = sessionEpochRef.current
    setIsRetryingAssistantSave(true)
    const retryPromise = (async () => {
      try {
        await appendMutation.mutateAsync({
          roomId: failedAssistantSave.roomId,
          messages: failedAssistantSave.messages,
        })
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        const savedRoomId = failedAssistantSave.roomId
        clearPendingMessageIds(savedRoomId, failedAssistantSave.messages)
        setFailedAssistantSave(null)
        setErrorMessage("")
        void requestGeneratedRoomTitle(savedRoomId)
        void refreshAssistantConversationSummary(savedRoomId, messageContextKey).catch(() => {})
        void queryClient.invalidateQueries({
          queryKey: messagesQueryKey(userKey, savedRoomId),
          exact: true,
        })
        return { ok: true }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(
            error?.message || "답변은 표시했지만 대화 이력을 저장하지 못했어요.",
          )
        }
        return { ok: false }
      }
    })()
    retryAssistantSavePromiseRef.current = retryPromise
    try {
      return await retryPromise
    } finally {
      if (retryAssistantSavePromiseRef.current === retryPromise) {
        retryAssistantSavePromiseRef.current = null
        if (isSessionCurrent(sessionEpoch)) setIsRetryingAssistantSave(false)
      }
    }
  }

  const discardFailedAssistantSave = () => {
    if (
      !failedAssistantSave ||
      failedAssistantSave.contextKey !== messageContextKey ||
      retryAssistantSavePromiseRef.current
    ) {
      return { ok: false }
    }
    const { roomId, messages: failedMessages } = failedAssistantSave
    clearPendingMessageIds(roomId, failedMessages)
    const failedMessageIds = new Set(failedMessages.map((message) => message.id))
    const remainingMessages = (messagesByRoomRef.current[roomId] || []).filter(
      (message) => !failedMessageIds.has(message.id),
    )
    messagesByRoomRef.current = {
      ...messagesByRoomRef.current,
      [roomId]: remainingMessages,
    }
    setMessagesByRoom((previous) => ({
      ...previous,
      [roomId]: remainingMessages,
    }))
    queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
      updateMessageQueryData(previous, roomId, remainingMessages),
    )
    setFailedAssistantSave(null)
    setErrorMessage("")
    return { ok: true }
  }

  const retryLastMessage = async () => {
    if (
      !failedRequest ||
      failedRequest.contextKey !== messageContextKey ||
      generationControllerRef.current
    ) {
      return { ok: false, accepted: false }
    }
    setActiveRoomId(failedRequest.roomId)
    return sendMessage(failedRequest.text, {
      roomId: failedRequest.roomId,
      reuseLastUserMessage: true,
    })
  }

  const editUserMessage = async (messageId, content) => {
    const roomId = activeRoomId
    const roomMessages = messagesByRoomRef.current[roomId] || []
    const messageIndex = roomMessages.findIndex(
      (message) => message.id === messageId && message.role === "user",
    )
    const text = typeof content === "string" ? content.trim() : ""
    if (!roomId || messageIndex < 0 || !text) return { ok: false, accepted: false }
    const baseMessages = roomMessages.slice(0, messageIndex)
    const parent = [...baseMessages].reverse().find((message) => !message.isGreeting)
    return sendMessage(text, {
      roomId,
      baseMessages,
      preparedUserMessage: {
        id: createMessageId("user"),
        role: "user",
        content: text,
        contextKey: messageContextKey,
        revisionOfId: messageId,
        parentId: parent?.id || null,
        createdAt: new Date().toISOString(),
      },
    })
  }

  const regenerateAssistantMessage = async (messageId) => {
    const roomId = activeRoomId
    const roomMessages = messagesByRoomRef.current[roomId] || []
    const assistantIndex = roomMessages.findIndex(
      (message) => message.id === messageId && message.role === "assistant",
    )
    if (!roomId || assistantIndex < 0) return { ok: false, accepted: false }
    let userIndex = assistantIndex - 1
    while (userIndex >= 0 && roomMessages[userIndex]?.role !== "user") userIndex -= 1
    if (userIndex < 0) return { ok: false, accepted: false }
    const userMessage = roomMessages[userIndex]
    return sendMessage(userMessage.content, {
      roomId,
      baseMessages: roomMessages.slice(0, userIndex + 1),
      reuseLastUserMessage: true,
    })
  }

  const rateAssistantMessage = async (messageId, rating) => {
    if (!activeRoomId || !messageId || !["up", "down", null].includes(rating)) return
    const roomId = activeRoomId
    const sessionEpoch = sessionEpochRef.current
    return enqueueByKey(
      feedbackQueueRef.current,
      `${roomId}:${messageId}`,
      async () => {
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        try {
          if (persistenceEnabled) {
            if (rating) {
              await submitAssistantMessageFeedback(roomId, messageId, { rating })
            } else {
              await deleteAssistantMessageFeedback(roomId, messageId)
            }
          }
          if (!isSessionCurrent(sessionEpoch)) return { ok: false }
          const nextRoomMessages = (
            messagesByRoomRef.current[roomId] || []
          ).map((message) =>
            message.id === messageId
              ? { ...message, feedback: rating ? { rating, reason: "" } : null }
              : message,
          )
          messagesByRoomRef.current = {
            ...messagesByRoomRef.current,
            [roomId]: nextRoomMessages,
          }
          setMessagesByRoom((previous) => ({
            ...previous,
            [roomId]: nextRoomMessages,
          }))
          queryClient.setQueryData(
            messagesQueryKey(userKey, roomId),
            (previous) =>
              updateMessageQueryData(previous, roomId, nextRoomMessages),
          )
          return { ok: true }
        } catch (error) {
          if (isSessionCurrent(sessionEpoch)) {
            setErrorMessage(error?.message || "답변 평가를 저장하지 못했어요.")
          }
          return { ok: false }
        }
      }
    )
  }

  const renameRoom = async (roomId, name) => {
    const normalizedName = typeof name === "string" ? name.trim() : ""
    if (!roomId || !normalizedName) return { ok: false }
    const sessionEpoch = sessionEpochRef.current
    return enqueueByKey(roomActionQueueRef.current, roomId, async () => {
      if (!isSessionCurrent(sessionEpoch)) return { ok: false }
      try {
        const currentRoom = roomsRef.current.find((room) => room.id === roomId)
        if (!currentRoom) return { ok: false }
        const updated = persistenceEnabled
          ? await updateAssistantConversation(roomId, { name: normalizedName })
          : { ...currentRoom, name: normalizedName }
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        replaceRoom(updated)
        return { ok: true }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화방 이름을 변경하지 못했어요.")
        }
        return { ok: false }
      }
    })
  }

  const togglePinRoom = async (roomId) => {
    if (!roomsRef.current.some((item) => item.id === roomId)) return { ok: false }
    const sessionEpoch = sessionEpochRef.current
    return enqueueByKey(roomActionQueueRef.current, roomId, async () => {
      if (!isSessionCurrent(sessionEpoch)) return { ok: false }
      try {
        const currentRoom = roomsRef.current.find((item) => item.id === roomId)
        if (!currentRoom) return { ok: false }
        const updated = persistenceEnabled
          ? await updateAssistantConversation(roomId, { pinned: !currentRoom.pinned })
          : { ...currentRoom, pinned: !currentRoom.pinned }
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        replaceRoom(updated)
        return { ok: true }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화방 고정 상태를 변경하지 못했어요.")
        }
        return { ok: false }
      }
    })
  }

  const toggleArchiveRoom = async (roomId) => {
    if (
      !roomsRef.current.some((item) => item.id === roomId) ||
      roomId === generationRoomId
    ) return { ok: false }
    const sessionEpoch = sessionEpochRef.current
    return enqueueByKey(roomActionQueueRef.current, roomId, async () => {
      if (!isSessionCurrent(sessionEpoch)) return { ok: false }
      try {
        const currentRoom = roomsRef.current.find((item) => item.id === roomId)
        if (!currentRoom) return { ok: false }
        const updated = persistenceEnabled
          ? await updateAssistantConversation(roomId, { archived: !currentRoom.archived })
          : {
              ...currentRoom,
              archived: !currentRoom.archived,
              updatedAt: new Date().toISOString(),
            }
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        const updatedRoom = normalizeRooms([updated])[0]
        if (persistenceEnabled && updatedRoom) {
          syncConversationRoomCaches(updatedRoom)
        }
        const remainingRooms = roomsRef.current.filter((item) => item.id !== roomId)
        roomsRef.current = remainingRooms
        setRooms(remainingRooms)
        const nextRoomListPage = {
          ...roomListPageRef.current,
          items: roomListPageRef.current.items.filter((item) => item.id !== roomId),
        }
        roomListPageRef.current = nextRoomListPage
        setRoomListPage(nextRoomListPage)
        setActiveRoomId((previous) =>
          previous === roomId ? remainingRooms[0]?.id || null : previous,
        )
        await queryClient.invalidateQueries({
          queryKey: ["assistant", "conversations", userKey],
        })
        return { ok: true }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화방 보관 상태를 변경하지 못했어요.")
        }
        return { ok: false }
      }
    })
  }

  const toggleArchivedView = () => {
    const nextArchived = !showArchived
    const cachedPage = queryClient.getQueryData(
      conversationsQueryKey(userKey, nextArchived),
    )
    const cachedRooms = Array.isArray(cachedPage) ? cachedPage : cachedPage?.results
    if (Array.isArray(cachedRooms)) {
      const nextRooms = normalizeRooms(cachedRooms).filter(
        (room) => !deletedRoomIdsRef.current.has(room.id),
      )
      setRooms(nextRooms)
      setRoomListPage({
        items: nextRooms,
        search: "",
        nextCursor:
          typeof cachedPage?.nextCursor === "string" ? cachedPage.nextCursor : "",
        hasMore: cachedPage?.hasMore === true,
        isLoadingMore: false,
        loadedFollowingPage: false,
      })
      setActiveRoomId((previous) =>
        nextRooms.some((room) => room.id === previous)
          ? previous
          : nextRooms[0]?.id || null,
      )
    }
    setShowArchived(nextArchived)
  }

  const downloadConversation = async (format) => {
    if (!activeRoomId || !persistenceEnabled) return
    try {
      await exportAssistantConversation(activeRoomId, format)
    } catch (error) {
      setErrorMessage(error?.message || "대화를 내보내지 못했어요.")
    }
  }

  const executeRemoveRooms = async (roomIds) => {
    const existingRoomIds = new Set(roomsRef.current.map((room) => room.id))
    const deletableRoomIds = normalizeList(roomIds).filter(
      (roomId) => roomId !== generationRoomId && existingRoomIds.has(roomId),
    )
    if (!deletableRoomIds.length) {
      return { deletedIds: [], failedIds: [] }
    }

    const sessionEpoch = sessionEpochRef.current
    try {
      roomSearchRequestRef.current += 1
      if (persistenceEnabled) {
        await queryClient.cancelQueries({
          queryKey: ["assistant", "conversations", userKey],
        })
        if (!isSessionCurrent(sessionEpoch)) {
          return { deletedIds: [], failedIds: deletableRoomIds }
        }
      }
      const result = persistenceEnabled
        ? await deleteMutation.mutateAsync(deletableRoomIds)
        : { deletedIds: deletableRoomIds, failedIds: [] }
      if (!isSessionCurrent(sessionEpoch)) {
        return { deletedIds: [], failedIds: deletableRoomIds }
      }
      const deletedRoomIdSet = new Set(result.deletedIds)
      result.deletedIds.forEach((roomId) => deletedRoomIdsRef.current.add(roomId))
      const remainingRooms = roomsRef.current.filter(
        (room) => !deletedRoomIdSet.has(room.id),
      )
      roomsRef.current = remainingRooms
      const remainingVisibleRooms = roomListPageRef.current.items.filter(
        (room) => !deletedRoomIdSet.has(room.id),
      )

      setRooms(remainingRooms)
      const nextRoomListPage = {
        ...roomListPageRef.current,
        items: remainingVisibleRooms,
      }
      roomListPageRef.current = nextRoomListPage
      setRoomListPage(nextRoomListPage)
      if (persistenceEnabled) {
        for (const archived of [false, true]) {
          queryClient.setQueryData(
            conversationsQueryKey(userKey, archived),
            (previous) => removeConversationIdsFromPage(previous, deletedRoomIdSet),
          )
        }
      }
      result.deletedIds.forEach((roomId) => {
        queryClient.removeQueries({ queryKey: messagesQueryKey(userKey, roomId) })
        pendingMessageIdsByRoomRef.current.delete(roomId)
      })
      const nextMessagesByRoom = { ...messagesByRoomRef.current }
      result.deletedIds.forEach((roomId) => delete nextMessagesByRoom[roomId])
      messagesByRoomRef.current = nextMessagesByRoom
      setMessagesByRoom(nextMessagesByRoom)
      const nextMessagePagesByRoom = { ...messagePagesByRoomRef.current }
      result.deletedIds.forEach((roomId) => delete nextMessagePagesByRoom[roomId])
      messagePagesByRoomRef.current = nextMessagePagesByRoom
      setMessagePagesByRoom(nextMessagePagesByRoom)
      setActiveRoomId((previous) =>
        deletedRoomIdSet.has(previous)
          ? remainingVisibleRooms[0]?.id || remainingRooms[0]?.id || null
          : previous,
      )
      if (result.failedIds.length) {
        setErrorMessage(
          `${result.failedIds.length}개 대화방을 삭제하지 못했어요. 다시 시도해주세요.`,
        )
      } else {
        setErrorMessage("")
      }
      if (persistenceEnabled) {
        await queryClient.invalidateQueries({
          queryKey: ["assistant", "conversations", userKey],
          refetchType: "none",
        })
      }
      return result
    } catch (error) {
      if (isSessionCurrent(sessionEpoch)) {
        setErrorMessage(error?.message || "대화방을 삭제하지 못했어요.")
      }
      return { deletedIds: [], failedIds: deletableRoomIds }
    }
  }

  const removeRooms = async (roomIds) => {
    const normalizedRoomIds = normalizeList(roomIds)
    const requestKey = [...normalizedRoomIds].sort().join(":")
    const activeRequest = removeRoomsPromiseRef.current
    if (activeRequest) {
      if (activeRequest.key === requestKey) return activeRequest.promise
      const queuedSessionEpoch = sessionEpochRef.current
      return activeRequest.promise.then(() =>
        isSessionCurrent(queuedSessionEpoch)
          ? removeRooms(normalizedRoomIds)
          : { deletedIds: [], failedIds: normalizedRoomIds },
      )
    }
    const sessionEpoch = sessionEpochRef.current
    setIsDeletingRooms(true)
    let removePromise
    removePromise = (async () => {
      try {
        return await executeRemoveRooms(normalizedRoomIds)
      } finally {
        if (removeRoomsPromiseRef.current?.promise === removePromise) {
          removeRoomsPromiseRef.current = null
          if (isSessionCurrent(sessionEpoch)) setIsDeletingRooms(false)
        }
      }
    })()
    removeRoomsPromiseRef.current = { key: requestKey, promise: removePromise }
    return removePromise
  }

  const removeRoom = async (roomId) => removeRooms([roomId])

  const messages = messagesByRoom[activeRoomId] || buildInitialMessages()
  const isSessionLoading =
    persistenceEnabled &&
    (conversationsQuery.isLoading || isHistoryLoading)
  const failedSaveRoom = failedAssistantSave
    ? rooms.find((room) => room.id === failedAssistantSave.roomId)
    : null
  const visibleErrorMessage = failedAssistantSave
    ? errorMessage ||
      `${failedSaveRoom?.name || "대화방"}의 답변을 저장하지 못했어요. 다시 시도하거나 제거해주세요.`
    : errorMessage

  return {
    rooms,
    roomListRooms: roomListPage.items,
    roomSearch: roomListPage.search,
    showArchived,
    hasMoreRooms: roomListPage.hasMore,
    isLoadingMoreRooms: roomListPage.isLoadingMore,
    activeRoomId,
    messages,
    messagesByRoom,
    isSending,
    isGenerating,
    hasActiveGeneration,
    generationRoomId,
    isRoomListBusy,
    isSessionLoading,
    errorMessage: visibleErrorMessage,
    canRetry: Boolean(failedRequest && failedRequest.contextKey === messageContextKey),
    canRetrySave: Boolean(
      failedAssistantSave && failedAssistantSave.contextKey === messageContextKey,
    ),
    clearError: () => setErrorMessage(""),
    sendMessage,
    retryAssistantSave,
    discardFailedAssistantSave,
    retryLastMessage,
    stopGenerating,
    resetConversation,
    editUserMessage,
    regenerateAssistantMessage,
    rateAssistantMessage,
    selectRoom,
    searchRooms,
    loadMoreRooms,
    hasOlderMessages: messagePagesByRoom[activeRoomId]?.hasMore === true,
    isLoadingOlderMessages:
      messagePagesByRoom[activeRoomId]?.isLoadingOlder === true,
    loadOlderMessages,
    createRoom,
    removeRoom,
    removeRooms,
    renameRoom,
    togglePinRoom,
    toggleArchiveRoom,
    toggleArchivedView,
    downloadConversation,
  }
}
