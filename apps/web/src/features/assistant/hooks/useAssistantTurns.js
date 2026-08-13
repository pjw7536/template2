import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { refreshAssistantConversationSummary } from "../api/conversationApi"
import {
  MAX_ASSISTANT_MESSAGE_CHARS,
  normalizeGeneratedAssistantMessage,
} from "../utils/chatLimits"
import { normalizeChatSources } from "../utils/normalizeChatSources"
import {
  copyProfileToolInputs,
  createMessageId,
  messagesQueryKey,
  updateMessageQueryData,
} from "../utils/assistantSessionModel"
import { useAssistantRun } from "./useAssistantRun"

export function useAssistantTurns({
  userKey,
  activeRoomId,
  setActiveRoomId,
  messageContextKey,
  profileKey,
  profileVersion,
  profileToolInputs,
  isHistoryLoading,
  hasResetInProgress,
  getOrCreateActiveRoomId,
  getRoomMessages,
  markPendingMessageIds,
  clearPendingMessageIds,
  touchRoom,
  requestGeneratedRoomTitle,
  getSessionEpoch,
  isSessionCurrent,
  setErrorMessage,
}) {
  const queryClient = useQueryClient()
  const assistantRun = useAssistantRun()
  const { stopRun } = assistantRun
  const sendMessagePromiseRef = useRef(null)
  const [failedRequest, setFailedRequest] = useState(null)
  const [generationRoomId, setGenerationRoomId] = useState(null)
  const [isPreparingSend, setIsPreparingSend] = useState(false)

  useEffect(() => {
    sendMessagePromiseRef.current = null
    setFailedRequest(null)
    setGenerationRoomId(null)
    setIsPreparingSend(false)
    stopRun()
  }, [stopRun, userKey])

  const executeSendMessage = async (input, options = {}) => {
    const sessionEpoch = options.sessionEpoch ?? getSessionEpoch()
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
    if (hasResetInProgress()) {
      setErrorMessage("대화 초기화가 끝난 뒤 메시지를 보내주세요.")
      return { ok: false, accepted: false }
    }
    if (assistantRun.isRunning || isHistoryLoading) {
      if (assistantRun.isRunning) {
        setErrorMessage("다른 대화방에서 답변을 생성하고 있어요.")
      }
      return { ok: false, accepted: false }
    }

    const roomId = await getOrCreateActiveRoomId(options.roomId)
    if (!roomId || !isSessionCurrent(sessionEpoch)) {
      return { ok: false, accepted: false }
    }
    await queryClient.cancelQueries({
      queryKey: messagesQueryKey(userKey, roomId),
      exact: true,
    })
    if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }

    const requestContextKey = options.contextKey || messageContextKey
    const requestProfileKey = options.profileKey || profileKey
    const requestProfileVersion = Number.isInteger(options.profileVersion)
      ? options.profileVersion
      : profileVersion
    const requestProfileToolInputs = copyProfileToolInputs(
      options.profileToolInputs ?? profileToolInputs,
    )
    const originalMessages = getRoomMessages(roomId)
    const currentMessages = Array.isArray(options.baseMessages)
      ? options.baseMessages
      : originalMessages
    const lastParentMessage = [...currentMessages]
      .reverse()
      .find((message) => !message.isGreeting)
    const userMessage = options.preparedUserMessage || {
      id: createMessageId("user"),
      role: "user",
      content: text,
      contextKey: requestContextKey,
      createdAt: new Date().toISOString(),
      ...(lastParentMessage ? { parentId: lastParentMessage.id } : {}),
    }
    const nextMessages = [...currentMessages, userMessage]
    markPendingMessageIds(roomId, [userMessage])
    const clientRequestId = `request-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

    queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
      updateMessageQueryData(previous, roomId, nextMessages),
    )
    touchRoom(roomId)
    setErrorMessage("")

    const streamingMessageId = createMessageId("assistant")
    const streamingMessageRef = { id: streamingMessageId }
    let streamedContent = ""
    let isStreamFinished = false
    let streamFramePending = false
    let cancelStreamFrame = () => {}
    markPendingMessageIds(roomId, [streamingMessageRef])
    setGenerationRoomId(roomId)
    setFailedRequest(null)

    const flushStreamDelta = () => {
      streamFramePending = false
      cancelStreamFrame = () => {}
      if (isStreamFinished || !isSessionCurrent(sessionEpoch)) return
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) => {
        const roomMessages = previous?.page?.results || nextMessages
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
          createdAt: new Date().toISOString(),
        }
        const updatedMessages = [...roomMessages]
        if (existingIndex >= 0) updatedMessages[existingIndex] = streamingMessage
        else updatedMessages.push(streamingMessage)
        return updateMessageQueryData(previous, roomId, updatedMessages)
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
      let completedMessage = null
      let runId = null
      await assistantRun.startRun(
        {
          action: options.turnAction || "send",
          conversationId: roomId,
          clientRequestId,
          profileKey: requestProfileKey,
          profileVersion: requestProfileVersion,
          appContextKey: requestContextKey,
          message: { clientId: userMessage.id, content: text },
          ...(options.targetMessageId
            ? { targetMessageId: options.targetMessageId }
            : {}),
          ...(options.retryRunId ? { retryRunId: options.retryRunId } : {}),
          toolInputs: requestProfileToolInputs,
        },
        {
          onEvent: ({ event, payload }) => {
            if (event === "run.started") runId = payload.runId || null
            else if (event === "message.delta") appendStreamDelta(payload.content)
            else if (event === "message.completed") completedMessage = payload
            else if (event === "run.failed") {
              const runError = new Error(payload.message || "Assistant Run에 실패했습니다.")
              runError.runId = payload.runId || runId
              throw runError
            }
          },
        },
      )
      if (!completedMessage) throw new Error("저장된 Assistant 답변을 받지 못했습니다.")
      isStreamFinished = true
      cancelStreamFrame()
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }

      const normalizedAssistantMessages = [
        normalizeGeneratedAssistantMessage({
          ...completedMessage,
          role: "assistant",
          content: completedMessage.content || streamedContent,
          sources: normalizeChatSources(completedMessage.sources),
          contextKey: completedMessage.contextKey || requestContextKey,
        }),
      ]
      clearPendingMessageIds(roomId, [streamingMessageRef])
      markPendingMessageIds(roomId, normalizedAssistantMessages)

      const latestMessages = getRoomMessages(roomId)
      const finalMessages = [
        ...latestMessages.filter((message) => message.id !== streamingMessageId),
        ...normalizedAssistantMessages.map((message) => ({
          ...message,
          isStreaming: false,
        })),
      ]
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
        updateMessageQueryData(previous, roomId, finalMessages),
      )
      touchRoom(roomId)
      clearPendingMessageIds(roomId, [userMessage, ...normalizedAssistantMessages])
      void requestGeneratedRoomTitle(roomId)
      void refreshAssistantConversationSummary(
        roomId,
        `profile:${requestProfileKey}`,
      ).catch(() => {})
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
      setFailedRequest(null)
      return { ok: true, accepted: true, roomId }
    } catch (error) {
      isStreamFinished = true
      cancelStreamFrame()
      if (!isSessionCurrent(sessionEpoch)) return { ok: false, accepted: false }
      const isCancelled = error?.name === "AbortError"
      clearPendingMessageIds(roomId, [userMessage, streamingMessageRef])
      const latestMessages = getRoomMessages(roomId)
      const messagesWithoutStream = latestMessages.filter(
        (message) => message.id !== streamingMessageId,
      )
      queryClient.setQueryData(messagesQueryKey(userKey, roomId), (previous) =>
        updateMessageQueryData(previous, roomId, messagesWithoutStream),
      )
      void queryClient.invalidateQueries({
        queryKey: messagesQueryKey(userKey, roomId),
        exact: true,
      })
      if (isCancelled) {
        setErrorMessage("")
        return { ok: true, accepted: true, cancelled: true, roomId }
      }
      setFailedRequest({
        roomId,
        text,
        contextKey: requestContextKey,
        profileKey: requestProfileKey,
        profileVersion: requestProfileVersion,
        profileToolInputs: requestProfileToolInputs,
        ...(error?.runId ? { retryRunId: error.runId } : {}),
      })
      setErrorMessage(error?.message || "메시지를 전송하지 못했어요.")
      return { ok: false, accepted: true, roomId }
    } finally {
      isStreamFinished = true
      cancelStreamFrame()
      setGenerationRoomId(null)
    }
  }

  const sendMessage = async (input, options = {}) => {
    if (sendMessagePromiseRef.current) {
      setErrorMessage(
        assistantRun.isRunning
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

  const retryLastMessage = async () => {
    if (!failedRequest || assistantRun.isRunning) {
      return { ok: false, accepted: false }
    }
    setActiveRoomId(failedRequest.roomId)
    return sendMessage(failedRequest.text, {
      roomId: failedRequest.roomId,
      contextKey: failedRequest.contextKey,
      profileKey: failedRequest.profileKey,
      profileVersion: failedRequest.profileVersion,
      profileToolInputs: failedRequest.profileToolInputs,
      ...(failedRequest.retryRunId
        ? { turnAction: "retry", retryRunId: failedRequest.retryRunId }
        : {}),
    })
  }

  const editUserMessage = async (messageId, content) => {
    const roomMessages = getRoomMessages(activeRoomId)
    const messageIndex = roomMessages.findIndex(
      (message) => message.id === messageId && message.role === "user",
    )
    const text = typeof content === "string" ? content.trim() : ""
    if (!activeRoomId || messageIndex < 0 || !text) return { ok: false, accepted: false }
    const baseMessages = roomMessages.slice(0, messageIndex)
    const parent = [...baseMessages].reverse().find((message) => !message.isGreeting)
    return sendMessage(text, {
      roomId: activeRoomId,
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
      turnAction: "edit",
      targetMessageId: messageId,
    })
  }

  const regenerateAssistantMessage = async (messageId) => {
    const roomMessages = getRoomMessages(activeRoomId)
    const assistantIndex = roomMessages.findIndex(
      (message) => message.id === messageId && message.role === "assistant",
    )
    if (!activeRoomId || assistantIndex < 0) return { ok: false, accepted: false }
    let userIndex = assistantIndex - 1
    while (userIndex >= 0 && roomMessages[userIndex]?.role !== "user") userIndex -= 1
    if (userIndex < 0) return { ok: false, accepted: false }
    const userMessage = roomMessages[userIndex]
    return sendMessage(userMessage.content, {
      roomId: activeRoomId,
      baseMessages: roomMessages.slice(0, userIndex),
      preparedUserMessage: {
        ...userMessage,
        id: createMessageId("user"),
        revisionOfId: userMessage.id,
        createdAt: new Date().toISOString(),
      },
      turnAction: "regenerate",
      targetMessageId: messageId,
    })
  }

  return {
    canRetry: Boolean(failedRequest),
    editUserMessage,
    generationRoomId,
    hasPendingSend: Boolean(sendMessagePromiseRef.current),
    isPreparingSend,
    isRunning: assistantRun.isRunning,
    regenerateAssistantMessage,
    retryLastMessage,
    sendMessage,
    stopGenerating: assistantRun.stopRun,
  }
}
