import { useCallback, useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  clearAssistantConversationMessages,
  deleteAssistantMessageFeedback,
  fetchAssistantConversationMessagePage,
  submitAssistantMessageFeedback,
} from "../api/conversationApi"
import {
  buildInitialMessages,
  enqueueByKey,
  mergeLatestMessagesPreservingOlder,
  mergeMessagesPreservingPending,
  messagesQueryKey,
  normalizeMessages,
  updateMessageQueryData,
} from "../utils/assistantSessionModel"

export function useAssistantMessages({
  userKey,
  activeRoomId,
  isSessionCurrent,
  getSessionEpoch,
  setErrorMessage,
}) {
  const queryClient = useQueryClient()
  const pendingMessageIdsByRoomRef = useRef(new Map())
  const loadOlderPromisesRef = useRef(new Map())
  const feedbackQueueRef = useRef(new Map())

  const messagesQuery = useQuery({
    queryKey: messagesQueryKey(userKey, activeRoomId),
    queryFn: async ({ signal }) => {
      const loadedPage = await fetchAssistantConversationMessagePage(activeRoomId, {
        signal,
      })
      const current = queryClient.getQueryData(
        messagesQueryKey(userKey, activeRoomId),
      )
      const currentMessages = current?.page?.results || []
      const serverMessages = buildInitialMessages(loadedPage.results)
      const hasAnimatedGreeting =
        loadedPage.results.length === 0
        && currentMessages.length === 1
        && Boolean(currentMessages[0]?.streamId)
      const pendingIds = new Set(
        pendingMessageIdsByRoomRef.current.get(activeRoomId) || [],
      )
      const mergedServerMessages = current?.page?.loadedOlderPage
        ? mergeLatestMessagesPreservingOlder(serverMessages, currentMessages)
        : serverMessages
      return {
        roomId: activeRoomId,
        page: {
          results: hasAnimatedGreeting
            ? currentMessages
            : mergeMessagesPreservingPending(
                mergedServerMessages,
                currentMessages,
                pendingIds,
              ),
          nextCursor: current?.page?.loadedOlderPage
            ? current.page.nextCursor
            : loadedPage.nextCursor,
          hasMore: current?.page?.loadedOlderPage
            ? current.page.hasMore
            : loadedPage.hasMore,
          loadedOlderPage: current?.page?.loadedOlderPage === true,
        },
      }
    },
    enabled: Boolean(activeRoomId),
  })

  useEffect(() => {
    const loadOlderPromises = loadOlderPromisesRef.current
    const feedbackQueue = feedbackQueueRef.current
    const pendingMessageIdsByRoom = pendingMessageIdsByRoomRef.current
    return () => {
      loadOlderPromises.clear()
      feedbackQueue.clear()
      pendingMessageIdsByRoom.clear()
    }
  }, [])

  useEffect(() => {
    loadOlderPromisesRef.current.clear()
    feedbackQueueRef.current.clear()
    pendingMessageIdsByRoomRef.current.clear()
  }, [userKey])

  useEffect(() => {
    if (messagesQuery.error) {
      setErrorMessage(
        messagesQuery.error.message || "대화 이력을 불러오지 못했어요.",
      )
    }
  }, [messagesQuery.error, setErrorMessage])

  const activePage = activeRoomId ? messagesQuery.data?.page : null
  const messages = activeRoomId
    ? activePage?.results || buildInitialMessages()
    : buildInitialMessages()
  const cachedMessageQueries = queryClient.getQueriesData({
    queryKey: ["assistant", "conversation-messages", userKey],
  })
  const messagesByRoom = Object.fromEntries(
    cachedMessageQueries.flatMap(([, cached]) =>
      cached?.roomId && Array.isArray(cached?.page?.results)
        ? [[cached.roomId, cached.page.results]]
        : [],
    ),
  )
  if (activeRoomId) messagesByRoom[activeRoomId] = messages

  const getRoomMessages = useCallback(
    (roomId) =>
      queryClient.getQueryData(messagesQueryKey(userKey, roomId))?.page?.results
      || buildInitialMessages(),
    [queryClient, userKey],
  )

  const markPendingMessageIds = useCallback((roomId, roomMessages) => {
    const pendingIds = new Set(pendingMessageIdsByRoomRef.current.get(roomId) || [])
    roomMessages.forEach((message) => {
      if (message?.id) pendingIds.add(message.id)
    })
    pendingMessageIdsByRoomRef.current.set(roomId, pendingIds)
  }, [])

  const clearPendingMessageIds = useCallback((roomId, roomMessages) => {
    const pendingIds = new Set(pendingMessageIdsByRoomRef.current.get(roomId) || [])
    roomMessages.forEach((message) => {
      if (message?.id) pendingIds.delete(message.id)
    })
    if (pendingIds.size) pendingMessageIdsByRoomRef.current.set(roomId, pendingIds)
    else pendingMessageIdsByRoomRef.current.delete(roomId)
  }, [])

  const initializeRoomMessages = useCallback(
    (roomId, { animateGreeting = false } = {}) => {
      pendingMessageIdsByRoomRef.current.delete(roomId)
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
        updateMessageQueryData(
          previous,
          roomId,
          buildInitialMessages([], { animateGreeting }),
        ),
      )
    },
    [queryClient, userKey],
  )

  const clearRoomMessages = useCallback(
    async (roomId) => {
      await clearAssistantConversationMessages(roomId)
      initializeRoomMessages(roomId)
    },
    [initializeRoomMessages],
  )

  const removeRoomMessageCache = useCallback(
    (roomId) => {
      queryClient.removeQueries({ queryKey: messagesQueryKey(userKey, roomId) })
      pendingMessageIdsByRoomRef.current.delete(roomId)
    },
    [queryClient, userKey],
  )

  const loadOlderMessages = useCallback(
    async (roomId = activeRoomId) => {
      const pendingPromise = loadOlderPromisesRef.current.get(roomId)
      if (pendingPromise) return pendingPromise
      const cached = queryClient.getQueryData(messagesQueryKey(userKey, roomId))
      const pageState = cached?.page
      if (
        !roomId
        || !pageState?.hasMore
        || !pageState.nextCursor
        || pageState.isLoadingOlder
      ) {
        return { ok: false, addedCount: 0 }
      }
      const sessionEpoch = getSessionEpoch()
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) => ({
        ...previous,
        page: { ...previous.page, isLoadingOlder: true },
      }))
      const loadPromise = (async () => {
        try {
          const page = await fetchAssistantConversationMessagePage(roomId, {
            before: pageState.nextCursor,
          })
          if (!isSessionCurrent(sessionEpoch)) return { ok: false, addedCount: 0 }
          const olderMessages = normalizeMessages(page.results)
          const currentRoomMessages = getRoomMessages(roomId)
          const addedMessages = olderMessages.filter(
            (message) => !currentRoomMessages.some((item) => item.id === message.id),
          )
          queryClient.setQueryData(messagesQueryKey(userKey, roomId), () => ({
            roomId,
            page: {
              results: [...addedMessages, ...currentRoomMessages],
              nextCursor: page.nextCursor,
              hasMore: page.hasMore,
              isLoadingOlder: false,
              loadedOlderPage: true,
            },
          }))
          return { ok: true, addedCount: addedMessages.length }
        } catch (error) {
          if (isSessionCurrent(sessionEpoch)) {
            queryClient.setQueryData(
              messagesQueryKey(userKey, roomId),
              (previous) => ({
                ...previous,
                page: { ...previous.page, isLoadingOlder: false },
              }),
            )
            setErrorMessage(error?.message || "이전 메시지를 불러오지 못했어요.")
          }
          return { ok: false, addedCount: 0 }
        }
      })()
      loadOlderPromisesRef.current.set(roomId, loadPromise)
      try {
        return await loadPromise
      } finally {
        if (loadOlderPromisesRef.current.get(roomId) === loadPromise) {
          loadOlderPromisesRef.current.delete(roomId)
        }
      }
    },
    [
      activeRoomId,
      getRoomMessages,
      getSessionEpoch,
      isSessionCurrent,
      queryClient,
      setErrorMessage,
      userKey,
    ],
  )

  const rateAssistantMessage = useCallback(
    async (messageId, rating) => {
      if (!activeRoomId || !messageId || !["up", "down", null].includes(rating)) return
      const roomId = activeRoomId
      const sessionEpoch = getSessionEpoch()
      return enqueueByKey(
        feedbackQueueRef.current,
        `${roomId}:${messageId}`,
        async () => {
          if (!isSessionCurrent(sessionEpoch)) return { ok: false }
          try {
            if (rating) {
              await submitAssistantMessageFeedback(roomId, messageId, { rating })
            } else {
              await deleteAssistantMessageFeedback(roomId, messageId)
            }
            if (!isSessionCurrent(sessionEpoch)) return { ok: false }
            const nextMessages = getRoomMessages(roomId).map((message) =>
              message.id === messageId
                ? { ...message, feedback: rating ? { rating, reason: "" } : null }
                : message,
            )
            queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
              updateMessageQueryData(previous, roomId, nextMessages),
            )
            return { ok: true }
          } catch (error) {
            if (isSessionCurrent(sessionEpoch)) {
              setErrorMessage(error?.message || "답변 평가를 저장하지 못했어요.")
            }
            return { ok: false }
          }
        },
      )
    },
    [
      activeRoomId,
      getRoomMessages,
      getSessionEpoch,
      isSessionCurrent,
      queryClient,
      setErrorMessage,
      userKey,
    ],
  )

  return {
    activePage,
    clearPendingMessageIds,
    clearRoomMessages,
    getRoomMessages,
    initializeRoomMessages,
    isHistoryLoading:
      Boolean(activeRoomId) && messagesQuery.isLoading && !activePage,
    loadOlderMessages,
    markPendingMessageIds,
    messages,
    messagesByRoom,
    rateAssistantMessage,
    removeRoomMessageCache,
  }
}
