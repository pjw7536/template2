import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createAssistantConversation,
  deleteAssistantConversation,
  exportAssistantConversation,
  fetchAssistantConversationPage,
  generateAssistantConversationTitle,
  updateAssistantConversation,
} from "../api/conversationApi"
import {
  conversationsQueryKey,
  enqueueByKey,
  isDefaultRoomName,
  mergeRoomsById,
  normalizeList,
  normalizeRooms,
  removeConversationIdsFromPage,
  updateConversationPageRoom,
} from "../utils/assistantSessionModel"

export function useAssistantConversations({
  userKey,
  activeRoomId,
  setActiveRoomId,
  initializeRoomMessages,
  removeRoomMessageCache,
  getGenerationRoomId,
  getSessionEpoch,
  isSessionCurrent,
  setErrorMessage,
}) {
  const queryClient = useQueryClient()
  const titleRequestRoomIdsRef = useRef(new Set())
  const createRoomPromiseRef = useRef(null)
  const removeRoomsPromiseRef = useRef(null)
  const loadMoreRoomsPromiseRef = useRef(null)
  const roomActionQueueRef = useRef(new Map())
  const deletedRoomIdsRef = useRef(new Set())
  const roomSearchRequestRef = useRef(0)
  const [roomSearch, setRoomSearch] = useState("")
  const [showArchived, setShowArchived] = useState(false)
  const [isCreatingRoom, setIsCreatingRoom] = useState(false)
  const [isDeletingRooms, setIsDeletingRooms] = useState(false)
  const [roomListMeta, setRoomListMeta] = useState({
    nextCursor: "",
    hasMore: false,
    isLoadingMore: false,
  })

  const conversationsQuery = useQuery({
    queryKey: conversationsQueryKey(userKey, showArchived, roomSearch),
    queryFn: async ({ signal }) => {
      const cacheKey = conversationsQueryKey(userKey, showArchived, roomSearch)
      const page = await fetchAssistantConversationPage({
        archived: showArchived,
        search: roomSearch,
        signal,
      })
      const current = queryClient.getQueryData(cacheKey)
      if (!current?.loadedFollowingPage) return page
      return {
        ...current,
        results: mergeRoomsById(page.results, current.results || []),
        loadedFollowingPage: true,
      }
    },
  })

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

  const rawRoomPage = conversationsQuery.data
  const rawRoomList = Array.isArray(rawRoomPage)
    ? rawRoomPage
    : rawRoomPage?.results
  const roomListRooms = normalizeRooms(rawRoomList || []).filter(
    (room) => !deletedRoomIdsRef.current.has(room.id),
  )
  const baseRoomPage = roomSearch
    ? queryClient.getQueryData(conversationsQueryKey(userKey, showArchived))
    : rawRoomPage
  const baseRoomList = Array.isArray(baseRoomPage)
    ? baseRoomPage
    : baseRoomPage?.results
  const rooms = mergeRoomsById(
    normalizeRooms(baseRoomList || []).filter(
      (room) => !deletedRoomIdsRef.current.has(room.id),
    ),
    roomListRooms,
  )
  const roomsRef = useRef(rooms)
  roomsRef.current = rooms

  useEffect(() => {
    const roomActionQueue = roomActionQueueRef.current
    return () => {
      roomActionQueue.clear()
      createRoomPromiseRef.current = null
      removeRoomsPromiseRef.current = null
      loadMoreRoomsPromiseRef.current = null
    }
  }, [])

  useEffect(() => {
    roomSearchRequestRef.current += 1
    setRoomSearch("")
    setShowArchived(false)
    setRoomListMeta({ nextCursor: "", hasMore: false, isLoadingMore: false })
    setIsCreatingRoom(false)
    setIsDeletingRooms(false)
    createRoomPromiseRef.current = null
    removeRoomsPromiseRef.current = null
    loadMoreRoomsPromiseRef.current = null
    roomActionQueueRef.current.clear()
    deletedRoomIdsRef.current.clear()
    titleRequestRoomIdsRef.current.clear()
  }, [userKey])

  useEffect(() => {
    if (!rawRoomPage) return
    setRoomListMeta({
      nextCursor:
        typeof rawRoomPage.nextCursor === "string" ? rawRoomPage.nextCursor : "",
      hasMore: rawRoomPage.hasMore === true,
      isLoadingMore: false,
    })
  }, [rawRoomPage])

  useEffect(() => {
    const pageRooms = Array.isArray(rawRoomPage)
      ? rawRoomPage
      : rawRoomPage?.results
    if (!Array.isArray(pageRooms)) return
    if (!pageRooms.some((room) => deletedRoomIdsRef.current.has(room?.id))) return
    queryClient.setQueryData(
      conversationsQueryKey(userKey, showArchived, roomSearch),
      (previous) => removeConversationIdsFromPage(previous, deletedRoomIdsRef.current),
    )
  }, [queryClient, rawRoomPage, roomSearch, showArchived, userKey])

  useEffect(() => {
    setActiveRoomId((previous) =>
      (rooms.some((room) => room.id === previous) && previous)
      || rooms[0]?.id
      || null,
    )
  }, [rooms, setActiveRoomId])

  useEffect(() => {
    if (conversationsQuery.error) {
      setErrorMessage(
        conversationsQuery.error.message || "대화 이력을 불러오지 못했어요.",
      )
    }
  }, [conversationsQuery.error, setErrorMessage])

  const getCachedRoom = useCallback(
    (roomId) => {
      for (const archived of [false, true]) {
        const cached = queryClient.getQueryData(
          conversationsQueryKey(userKey, archived),
        )
        const cachedRooms = Array.isArray(cached) ? cached : cached?.results
        const found = normalizeRooms(cachedRooms || []).find(
          (room) => room.id === roomId,
        )
        if (found) return found
      }
      return null
    },
    [queryClient, userKey],
  )

  const syncConversationRoomCaches = useCallback(
    (room) => {
      const normalizedRoom = normalizeRooms([room])[0]
      if (!normalizedRoom) return
      queryClient.setQueryData(
        conversationsQueryKey(userKey, false),
        (previous) => updateConversationPageRoom(previous, normalizedRoom, {
          include: !normalizedRoom.archived,
        }),
      )
      queryClient.setQueryData(
        conversationsQueryKey(userKey, true),
        (previous) => updateConversationPageRoom(previous, normalizedRoom, {
          include: normalizedRoom.archived,
        }),
      )
    },
    [queryClient, userKey],
  )

  const replaceRoom = useCallback(
    (room) => {
      const normalizedRoom = normalizeRooms([room])[0]
      if (normalizedRoom) syncConversationRoomCaches(normalizedRoom)
    },
    [syncConversationRoomCaches],
  )

  const touchRoom = useCallback(
    (roomId) => {
      const room = getCachedRoom(roomId)
      if (!room) return
      syncConversationRoomCaches({ ...room, updatedAt: new Date().toISOString() })
    },
    [getCachedRoom, syncConversationRoomCaches],
  )

  const requestGeneratedRoomTitle = useCallback(
    async (roomId) => {
      if (titleRequestRoomIdsRef.current.has(roomId)) return
      const sessionEpoch = getSessionEpoch()
      const room = getCachedRoom(roomId)
      if (!room || !isDefaultRoomName(room.name)) return
      titleRequestRoomIdsRef.current.add(roomId)
      try {
        const titledRoom = normalizeRooms([
          await generateAssistantConversationTitle(roomId),
        ])[0]
        if (titledRoom && isSessionCurrent(sessionEpoch)) replaceRoom(titledRoom)
      } catch {
        // 제목 생성 실패는 채팅 답변과 메시지 저장 성공에 영향을 주지 않습니다.
      } finally {
        titleRequestRoomIdsRef.current.delete(roomId)
      }
    },
    [getCachedRoom, getSessionEpoch, isSessionCurrent, replaceRoom],
  )

  const createRoom = useCallback(
    async (label) => {
      if (createRoomPromiseRef.current) return createRoomPromiseRef.current
      if (conversationsQuery.isLoading) return null
      const sessionEpoch = getSessionEpoch()
      setIsCreatingRoom(true)
      const createPromise = (async () => {
        await queryClient.cancelQueries({
          queryKey: ["assistant", "conversations", userKey],
        })
        if (!isSessionCurrent(sessionEpoch)) return null
        if (showArchived) setShowArchived(false)
        if (roomSearch) setRoomSearch("")
        const name = typeof label === "string" && label.trim()
          ? label.trim()
          : `새 대화 ${roomsRef.current.length + 1}`
        const created = await createAssistantConversation({ name })
        if (!isSessionCurrent(sessionEpoch)) return null
        const room = normalizeRooms([created])[0]
        if (!room) throw new Error("생성된 대화방 정보가 올바르지 않습니다.")
        setActiveRoomId(room.id)
        syncConversationRoomCaches(room)
        initializeRoomMessages(room.id, { animateGreeting: true })
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
      getSessionEpoch,
      initializeRoomMessages,
      isSessionCurrent,
      queryClient,
      roomSearch,
      setActiveRoomId,
      setErrorMessage,
      showArchived,
      syncConversationRoomCaches,
      userKey,
    ],
  )

  const getOrCreateActiveRoomId = useCallback(
    async (preferredRoomId) => {
      if (preferredRoomId && roomsRef.current.some((room) => room.id === preferredRoomId)) {
        return preferredRoomId
      }
      if (activeRoomId && roomsRef.current.some((room) => room.id === activeRoomId)) {
        return activeRoomId
      }
      return roomsRef.current[0]?.id || createRoom()
    },
    [activeRoomId, createRoom],
  )

  const selectRoom = useCallback(
    (roomId) => {
      if (!roomsRef.current.some((room) => room.id === roomId)) return
      setActiveRoomId(roomId)
      setErrorMessage("")
    },
    [setActiveRoomId, setErrorMessage],
  )

  const searchRooms = useCallback((search = "") => {
    roomSearchRequestRef.current += 1
    setRoomListMeta({ nextCursor: "", hasMore: false, isLoadingMore: true })
    setRoomSearch(String(search || "").trim())
  }, [])

  const loadMoreRooms = useCallback(async () => {
    if (loadMoreRoomsPromiseRef.current) return loadMoreRoomsPromiseRef.current
    const pageState = roomListMeta
    if (!pageState.hasMore || !pageState.nextCursor || pageState.isLoadingMore) {
      return { ok: false, addedCount: 0 }
    }
    const sessionEpoch = getSessionEpoch()
    const searchRequestId = roomSearchRequestRef.current
    setRoomListMeta((previous) => ({ ...previous, isLoadingMore: true }))
    const loadPromise = (async () => {
      try {
        const page = await fetchAssistantConversationPage({
          search: roomSearch,
          cursor: pageState.nextCursor,
          archived: showArchived,
        })
        if (
          !isSessionCurrent(sessionEpoch)
          || searchRequestId !== roomSearchRequestRef.current
        ) return { ok: false, addedCount: 0 }
        const pageRooms = normalizeRooms(page.results).filter(
          (room) => !deletedRoomIdsRef.current.has(room.id),
        )
        const cacheKey = conversationsQueryKey(userKey, showArchived, roomSearch)
        const previousPage = queryClient.getQueryData(cacheKey)
        const previousRooms = Array.isArray(previousPage)
          ? previousPage
          : previousPage?.results || []
        const addedRooms = pageRooms.filter(
          (room) => !previousRooms.some((item) => item.id === room.id),
        )
        queryClient.setQueryData(cacheKey, {
          ...(Array.isArray(previousPage) ? {} : previousPage),
          results: [...previousRooms, ...addedRooms],
          nextCursor: page.nextCursor,
          hasMore: page.hasMore,
          loadedFollowingPage: true,
        })
        setRoomListMeta({
          nextCursor: page.nextCursor,
          hasMore: page.hasMore,
          isLoadingMore: false,
        })
        return { ok: true, addedCount: addedRooms.length }
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setRoomListMeta((previous) => ({ ...previous, isLoadingMore: false }))
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
  }, [
    getSessionEpoch,
    isSessionCurrent,
    queryClient,
    roomListMeta,
    roomSearch,
    setErrorMessage,
    showArchived,
    userKey,
  ])

  const updateRoom = useCallback(
    (roomId, updatesOrFactory, errorMessage) =>
      enqueueByKey(roomActionQueueRef.current, roomId, async () => {
        const sessionEpoch = getSessionEpoch()
        if (!isSessionCurrent(sessionEpoch)) return { ok: false }
        try {
          const currentRoom = getCachedRoom(roomId)
          if (!currentRoom) return { ok: false }
          const updates = typeof updatesOrFactory === "function"
            ? updatesOrFactory(currentRoom)
            : updatesOrFactory
          const updated = await updateAssistantConversation(roomId, updates)
          if (!isSessionCurrent(sessionEpoch)) return { ok: false }
          replaceRoom(updated)
          return { ok: true, room: updated }
        } catch (error) {
          if (isSessionCurrent(sessionEpoch)) {
            setErrorMessage(error?.message || errorMessage)
          }
          return { ok: false }
        }
      }),
    [
      getCachedRoom,
      getSessionEpoch,
      isSessionCurrent,
      replaceRoom,
      setErrorMessage,
    ],
  )

  const renameRoom = useCallback(
    async (roomId, name) => {
      const normalizedName = typeof name === "string" ? name.trim() : ""
      if (!roomId || !normalizedName) return { ok: false }
      return updateRoom(
        roomId,
        { name: normalizedName },
        "대화방 이름을 변경하지 못했어요.",
      )
    },
    [updateRoom],
  )

  const togglePinRoom = useCallback(
    async (roomId) => {
      return updateRoom(
        roomId,
        (room) => ({ pinned: !room.pinned }),
        "대화방 고정 상태를 변경하지 못했어요.",
      )
    },
    [updateRoom],
  )

  const toggleArchiveRoom = useCallback(
    async (roomId) => {
      if (roomId === getGenerationRoomId()) return { ok: false }
      const result = await updateRoom(
        roomId,
        (room) => ({ archived: !room.archived }),
        "대화방 보관 상태를 변경하지 못했어요.",
      )
      if (!result.ok) return result
      const remainingRooms = roomsRef.current.filter((item) => item.id !== roomId)
      setActiveRoomId((previous) =>
        previous === roomId ? remainingRooms[0]?.id || null : previous,
      )
      await queryClient.invalidateQueries({
        queryKey: ["assistant", "conversations", userKey],
      })
      return result
    },
    [
      getGenerationRoomId,
      queryClient,
      setActiveRoomId,
      updateRoom,
      userKey,
    ],
  )

  const toggleArchivedView = useCallback(() => {
    setRoomSearch("")
    setRoomListMeta({ nextCursor: "", hasMore: false, isLoadingMore: false })
    setShowArchived((previous) => !previous)
  }, [])

  const downloadConversation = useCallback(
    async (format) => {
      if (!activeRoomId) return
      try {
        await exportAssistantConversation(activeRoomId, format)
      } catch (error) {
        setErrorMessage(error?.message || "대화를 내보내지 못했어요.")
      }
    },
    [activeRoomId, setErrorMessage],
  )

  const executeRemoveRooms = useCallback(
    async (roomIds) => {
      const existingRoomIds = new Set(roomsRef.current.map((room) => room.id))
      const generationRoomId = getGenerationRoomId()
      const deletableRoomIds = normalizeList(roomIds).filter(
        (roomId) => roomId !== generationRoomId && existingRoomIds.has(roomId),
      )
      if (!deletableRoomIds.length) return { deletedIds: [], failedIds: [] }
      const sessionEpoch = getSessionEpoch()
      try {
        roomSearchRequestRef.current += 1
        await queryClient.cancelQueries({
          queryKey: ["assistant", "conversations", userKey],
        })
        if (!isSessionCurrent(sessionEpoch)) {
          return { deletedIds: [], failedIds: deletableRoomIds }
        }
        const result = await deleteMutation.mutateAsync(deletableRoomIds)
        if (!isSessionCurrent(sessionEpoch)) {
          return { deletedIds: [], failedIds: deletableRoomIds }
        }
        const deletedIds = new Set(result.deletedIds)
        result.deletedIds.forEach((roomId) => deletedRoomIdsRef.current.add(roomId))
        const remainingRooms = roomsRef.current.filter((room) => !deletedIds.has(room.id))
        const remainingVisibleRooms = roomListRooms.filter((room) => !deletedIds.has(room.id))
        queryClient.setQueriesData(
          { queryKey: ["assistant", "conversations", userKey] },
          (previous) => removeConversationIdsFromPage(previous, deletedIds),
        )
        result.deletedIds.forEach(removeRoomMessageCache)
        setActiveRoomId((previous) =>
          deletedIds.has(previous)
            ? remainingVisibleRooms[0]?.id || remainingRooms[0]?.id || null
            : previous,
        )
        setErrorMessage(
          result.failedIds.length
            ? `${result.failedIds.length}개 대화방을 삭제하지 못했어요. 다시 시도해주세요.`
            : "",
        )
        await queryClient.invalidateQueries({
          queryKey: ["assistant", "conversations", userKey],
          refetchType: "none",
        })
        return result
      } catch (error) {
        if (isSessionCurrent(sessionEpoch)) {
          setErrorMessage(error?.message || "대화방을 삭제하지 못했어요.")
        }
        return { deletedIds: [], failedIds: deletableRoomIds }
      }
    },
    [
      deleteMutation,
      getGenerationRoomId,
      getSessionEpoch,
      isSessionCurrent,
      queryClient,
      removeRoomMessageCache,
      roomListRooms,
      setActiveRoomId,
      setErrorMessage,
      userKey,
    ],
  )

  const removeRooms = useCallback(
    async (roomIds) => {
      const normalizedRoomIds = normalizeList(roomIds)
      const requestKey = [...normalizedRoomIds].sort().join(":")
      const activeRequest = removeRoomsPromiseRef.current
      if (activeRequest) {
        if (activeRequest.key === requestKey) return activeRequest.promise
        const sessionEpoch = getSessionEpoch()
        return activeRequest.promise.then(() =>
          isSessionCurrent(sessionEpoch)
            ? removeRooms(normalizedRoomIds)
            : { deletedIds: [], failedIds: normalizedRoomIds },
        )
      }
      const sessionEpoch = getSessionEpoch()
      setIsDeletingRooms(true)
      let removePromise
      removePromise = executeRemoveRooms(normalizedRoomIds).finally(() => {
        if (removeRoomsPromiseRef.current?.promise === removePromise) {
          removeRoomsPromiseRef.current = null
          if (isSessionCurrent(sessionEpoch)) setIsDeletingRooms(false)
        }
      })
      removeRoomsPromiseRef.current = { key: requestKey, promise: removePromise }
      return removePromise
    },
    [executeRemoveRooms, getSessionEpoch, isSessionCurrent],
  )

  return {
    activeRoomId,
    createRoom,
    createRoomInProgress: Boolean(createRoomPromiseRef.current),
    downloadConversation,
    getOrCreateActiveRoomId,
    hasMoreRooms: roomListMeta.hasMore,
    isCreatingRoom,
    isDeletingRooms,
    isLoading: conversationsQuery.isLoading,
    isLoadingMoreRooms: roomListMeta.isLoadingMore,
    loadMoreRooms,
    removeRoom: (roomId) => removeRooms([roomId]),
    removeRooms,
    renameRoom,
    requestGeneratedRoomTitle,
    roomListRooms,
    rooms,
    roomSearch,
    searchRooms,
    selectRoom,
    showArchived,
    toggleArchiveRoom,
    toggleArchivedView,
    togglePinRoom,
    touchRoom,
  }
}
