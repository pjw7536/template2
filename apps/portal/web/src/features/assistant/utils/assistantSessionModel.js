import { normalizeChatSources } from "./normalizeChatSources"
import { sortRoomsByRecentQuestion } from "./chatRooms"

const DEFAULT_ROOM_NAME_PATTERN = /^새 대화(?:\s+\d+)?$/

export function normalizeList(values) {
  if (!Array.isArray(values)) return []
  return Array.from(
    new Set(
      values
        .map((value) => (typeof value === "string" ? value.trim() : ""))
        .filter(Boolean),
    ),
  )
}

export function copyProfileToolInputs(value) {
  if (!value || typeof value !== "object") return {}
  return JSON.parse(JSON.stringify(value))
}

export function createMessageId(role) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

export function normalizeMessages(messages) {
  if (!Array.isArray(messages)) return []
  return messages
    .map((message) => {
      const role = typeof message?.role === "string" ? message.role : ""
      const accessState = message?.accessState === "locked" ? "locked" : "available"
      const content =
        accessState === "locked"
          ? "현재 권한으로 볼 수 없는 메시지입니다."
          : typeof message?.content === "string"
            ? message.content.trim()
            : ""
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
        accessState,
        blocks: Array.isArray(message.blocks) ? message.blocks : [],
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

export function buildInitialMessages(messages, { animateGreeting = false } = {}) {
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

export function normalizeRooms(rawRooms) {
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

export function isDefaultRoomName(name) {
  return typeof name === "string" && DEFAULT_ROOM_NAME_PATTERN.test(name.trim())
}

export function conversationsQueryKey(userKey, archived = false, search = "") {
  const baseKey = [
    "assistant",
    "conversations",
    userKey,
    archived ? "archived" : "active",
  ]
  return search ? [...baseKey, "search", search] : baseKey
}

export function messagesQueryKey(userKey, roomId) {
  return ["assistant", "conversation-messages", userKey, roomId]
}

export function mergeRoomsById(primaryRooms, additionalRooms) {
  const knownIds = new Set(primaryRooms.map((room) => room.id))
  return [
    ...primaryRooms,
    ...additionalRooms.filter((room) => !knownIds.has(room.id)),
  ]
}

export function updateConversationPageRoom(previous, room, { include }) {
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

export function updateMessageQueryData(previous, roomId, messages) {
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

export function mergeMessagesPreservingPending(serverMessages, localMessages, pendingIds) {
  const hasLocalChanges =
    pendingIds.size > 0 || localMessages.some((message) => message.isStreaming === true)
  return hasLocalChanges ? localMessages : serverMessages
}

export function mergeLatestMessagesPreservingOlder(serverMessages, localMessages) {
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

export function removeConversationIdsFromPage(previous, deletedIds) {
  if (!previous) return previous
  const previousRooms = Array.isArray(previous) ? previous : previous.results
  if (!Array.isArray(previousRooms)) return previous
  const results = previousRooms.filter((room) => !deletedIds.has(room.id))
  return Array.isArray(previous) ? results : { ...previous, results }
}

export function enqueueByKey(queue, key, task) {
  const previous = queue.get(key) || Promise.resolve()
  const queued = previous.catch(() => undefined).then(task)
  queue.set(key, queued)
  return queued.finally(() => {
    if (queue.get(key) === queued) queue.delete(key)
  })
}
