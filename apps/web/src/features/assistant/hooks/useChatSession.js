import { useCallback, useEffect, useRef, useState } from "react"

import { useAssistantConversations } from "./useAssistantConversations"
import { useAssistantMessages } from "./useAssistantMessages"
import { useAssistantTurns } from "./useAssistantTurns"

export function useChatSession(options = {}) {
  const userKey = String(options.userKey || "").trim()
  if (!userKey) throw new Error("Assistant userKey가 필요합니다.")

  const messageContextKey =
    typeof options.messageContextKey === "string" && options.messageContextKey
      ? options.messageContextKey
      : ""
  if (!messageContextKey) throw new Error("Assistant messageContextKey가 필요합니다.")

  const profileKey = String(options.profileKey || "").trim()
  if (!profileKey) throw new Error("Assistant profileKey가 필요합니다.")

  const profileVersion = Number.isInteger(options.profileVersion)
    ? options.profileVersion
    : 1
  const profileToolInputs =
    options.profileToolInputs && typeof options.profileToolInputs === "object"
      ? options.profileToolInputs
      : {}

  const userKeyRef = useRef(userKey)
  const sessionEpochRef = useRef(0)
  const isMountedRef = useRef(true)
  const resetConversationPromiseRef = useRef(null)
  const generationRoomIdRef = useRef(null)
  const [activeRoomId, setActiveRoomId] = useState(null)
  const [errorMessage, setErrorMessage] = useState("")
  const [isResettingConversation, setIsResettingConversation] = useState(false)

  const getSessionEpoch = useCallback(() => sessionEpochRef.current, [])
  const getGenerationRoomId = useCallback(
    () => generationRoomIdRef.current,
    [],
  )
  const hasResetInProgress = useCallback(
    () => Boolean(resetConversationPromiseRef.current),
    [],
  )
  const isSessionCurrent = useCallback(
    (sessionEpoch) =>
      isMountedRef.current && sessionEpochRef.current === sessionEpoch,
    [],
  )

  const messageSession = useAssistantMessages({
    userKey,
    activeRoomId,
    getSessionEpoch,
    isSessionCurrent,
    setErrorMessage,
  })

  const conversationSession = useAssistantConversations({
    userKey,
    activeRoomId,
    setActiveRoomId,
    initializeRoomMessages: messageSession.initializeRoomMessages,
    removeRoomMessageCache: messageSession.removeRoomMessageCache,
    getGenerationRoomId,
    getSessionEpoch,
    isSessionCurrent,
    setErrorMessage,
  })

  const turnSession = useAssistantTurns({
    userKey,
    activeRoomId,
    setActiveRoomId,
    messageContextKey,
    profileKey,
    profileVersion,
    profileToolInputs,
    isHistoryLoading: messageSession.isHistoryLoading,
    hasResetInProgress,
    getOrCreateActiveRoomId: conversationSession.getOrCreateActiveRoomId,
    getRoomMessages: messageSession.getRoomMessages,
    markPendingMessageIds: messageSession.markPendingMessageIds,
    clearPendingMessageIds: messageSession.clearPendingMessageIds,
    touchRoom: conversationSession.touchRoom,
    requestGeneratedRoomTitle: conversationSession.requestGeneratedRoomTitle,
    getSessionEpoch,
    isSessionCurrent,
    setErrorMessage,
  })
  generationRoomIdRef.current = turnSession.generationRoomId
  const {
    createRoomInProgress,
    rooms,
    touchRoom,
  } = conversationSession
  const { clearRoomMessages } = messageSession

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      sessionEpochRef.current += 1
      resetConversationPromiseRef.current = null
    }
  }, [])

  useEffect(() => {
    if (userKeyRef.current === userKey) return
    sessionEpochRef.current += 1
    userKeyRef.current = userKey
    setActiveRoomId(null)
    setErrorMessage("")
    setIsResettingConversation(false)
    resetConversationPromiseRef.current = null
  }, [userKey])

  const resetConversation = useCallback(
    async (roomId = activeRoomId) => {
      if (resetConversationPromiseRef.current) {
        return resetConversationPromiseRef.current
      }
      const targetRoomId = rooms.some(
        (room) => room.id === roomId,
      )
        ? roomId
        : null
      if (!targetRoomId) return { ok: false }
      if (
        turnSession.hasPendingSend
        || createRoomInProgress
        || turnSession.isRunning
      ) {
        setErrorMessage("답변 생성이 끝난 뒤 대화를 초기화해주세요.")
        return { ok: false }
      }
      const sessionEpoch = getSessionEpoch()
      setIsResettingConversation(true)
      const resetPromise = (async () => {
        try {
          await clearRoomMessages(targetRoomId)
          if (!isSessionCurrent(sessionEpoch)) return { ok: false }
          touchRoom(targetRoomId)
          setErrorMessage("")
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
          if (isSessionCurrent(sessionEpoch)) setIsResettingConversation(false)
        }
      }
    },
    [
      activeRoomId,
      clearRoomMessages,
      createRoomInProgress,
      getSessionEpoch,
      isSessionCurrent,
      rooms,
      touchRoom,
      turnSession.hasPendingSend,
      turnSession.isRunning,
    ],
  )

  const hasActiveGeneration = Boolean(turnSession.generationRoomId)
  const isSending =
    turnSession.isPreparingSend
    || isResettingConversation
    || hasActiveGeneration
    || conversationSession.isCreatingRoom
    || conversationSession.isLoading
    || messageSession.isHistoryLoading
  const isRoomListBusy =
    conversationSession.isCreatingRoom
    || isResettingConversation
    || conversationSession.isDeletingRooms
    || conversationSession.isLoading

  return {
    rooms: conversationSession.rooms,
    roomListRooms: conversationSession.roomListRooms,
    roomSearch: conversationSession.roomSearch,
    showArchived: conversationSession.showArchived,
    hasMoreRooms: conversationSession.hasMoreRooms,
    isLoadingMoreRooms: conversationSession.isLoadingMoreRooms,
    activeRoomId,
    messages: messageSession.messages,
    messagesByRoom: messageSession.messagesByRoom,
    isSending,
    isGenerating:
      hasActiveGeneration && turnSession.generationRoomId === activeRoomId,
    hasActiveGeneration,
    generationRoomId: turnSession.generationRoomId,
    isRoomListBusy,
    isSessionLoading:
      conversationSession.isLoading || messageSession.isHistoryLoading,
    errorMessage,
    canRetry: turnSession.canRetry,
    clearError: () => setErrorMessage(""),
    sendMessage: turnSession.sendMessage,
    retryLastMessage: turnSession.retryLastMessage,
    stopGenerating: turnSession.stopGenerating,
    resetConversation,
    editUserMessage: turnSession.editUserMessage,
    regenerateAssistantMessage: turnSession.regenerateAssistantMessage,
    rateAssistantMessage: messageSession.rateAssistantMessage,
    selectRoom: conversationSession.selectRoom,
    searchRooms: conversationSession.searchRooms,
    loadMoreRooms: conversationSession.loadMoreRooms,
    hasOlderMessages: messageSession.activePage?.hasMore === true,
    isLoadingOlderMessages:
      messageSession.activePage?.isLoadingOlder === true,
    loadOlderMessages: messageSession.loadOlderMessages,
    createRoom: conversationSession.createRoom,
    removeRoom: conversationSession.removeRoom,
    removeRooms: conversationSession.removeRooms,
    renameRoom: conversationSession.renameRoom,
    togglePinRoom: conversationSession.togglePinRoom,
    toggleArchiveRoom: conversationSession.toggleArchiveRoom,
    toggleArchivedView: conversationSession.toggleArchivedView,
    downloadConversation: conversationSession.downloadConversation,
  }
}
