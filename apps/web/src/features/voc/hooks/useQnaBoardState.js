// src/features/voc/hooks/useQnaBoardState.js
// Q&A 게시판 상태/동작을 캡슐화한 훅
import * as React from "react"

import { DEFAULT_STATUS, STATUS_OPTIONS } from "../constants"
import {
  createVocPost,
  createVocReply,
  deleteVocPost,
  fetchVocPosts,
  updateVocPost,
} from "../api/voc"
import { hasMeaningfulContent, sanitizeContentHtml } from "../utils"

export function useQnaBoardState({ currentUser, isAdmin }) {
  const [posts, setPosts] = React.useState([])
  const [statusFilter, setStatusFilter] = React.useState(null)
  const [form, setForm] = React.useState({ title: "", content: "" })
  const [replyDrafts, setReplyDrafts] = React.useState({})
  const [selectedPostId, setSelectedPostId] = React.useState(null)
  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize: 8 })
  const [isDetailOpen, setIsDetailOpen] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [isUpdating, setIsUpdating] = React.useState(false)

  const statusCounts = React.useMemo(
    () =>
      STATUS_OPTIONS.reduce(
        (acc, option) => ({
          ...acc,
          [option.value]: posts.filter((post) => post.status === option.value).length,
        }),
        {},
      ),
    [posts],
  )

  const filteredPosts = React.useMemo(() => {
    if (!statusFilter) return posts
    return posts.filter((post) => post.status === statusFilter)
  }, [posts, statusFilter])

  const visiblePosts = React.useMemo(() => {
    const start = pagination.pageIndex * pagination.pageSize
    const end = start + pagination.pageSize
    return filteredPosts.slice(start, end)
  }, [filteredPosts, pagination.pageIndex, pagination.pageSize])

  const pageCount = Math.max(Math.ceil((filteredPosts.length || 1) / pagination.pageSize), 1)
  const currentPage = pagination.pageIndex + 1
  const totalPages = pageCount

  const selectedPost = React.useMemo(
    () => posts.find((post) => post.id === selectedPostId) || null,
    [posts, selectedPostId],
  )

  const clearSelection = React.useCallback(() => {
    setSelectedPostId(null)
    setIsDetailOpen(false)
  }, [])

  const canDeletePost = React.useCallback(
    (post) => {
      if (isAdmin) return true
      const authorKey = post.author?.id || post.author?.email || post.author?.name
      return Boolean(authorKey && authorKey === currentUser.id)
    },
    [currentUser.id, isAdmin],
  )

  const loadPosts = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { posts: loadedPosts } = await fetchVocPosts()
      const normalizedPosts = (loadedPosts || []).map((post) => ({
        ...post,
        content: sanitizeContentHtml(post.content),
      }))
      setPosts(normalizedPosts)
    } catch (err) {
      setError(err?.message || "VOC 데이터를 불러오지 못했습니다.")
      setPosts([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadPosts()
  }, [loadPosts])

  React.useEffect(() => {
    if (!selectedPostId) return
    const exists = posts.some((post) => post.id === selectedPostId)
    if (!exists) {
      setSelectedPostId(null)
      setIsDetailOpen(false)
    }
  }, [posts, selectedPostId])

  React.useEffect(() => {
    const lastPageIndex = Math.max(
      Math.ceil((filteredPosts.length || 1) / pagination.pageSize) - 1,
      0,
    )
    if (pagination.pageIndex > lastPageIndex) {
      setPagination((prev) => ({ ...prev, pageIndex: lastPageIndex }))
    }
  }, [filteredPosts.length, pagination.pageIndex, pagination.pageSize])

  const updateForm = React.useCallback((key, valueOrUpdater) => {
    setForm((prev) => {
      const nextValue =
        typeof valueOrUpdater === "function" ? valueOrUpdater(prev[key]) : valueOrUpdater
      return { ...prev, [key]: nextValue }
    })
  }, [])

  const resetForm = React.useCallback(() => {
    setForm({ title: "", content: "" })
  }, [])

  const toggleStatusFilter = React.useCallback((status) => {
    setStatusFilter((prev) => (prev === status ? null : status))
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
  }, [])

  const createPost = React.useCallback(async () => {
    const title = form.title.trim()
    const content = sanitizeContentHtml(form.content)
    const status = DEFAULT_STATUS
    if (!title || !hasMeaningfulContent(content, { skipSanitize: true }) || !status) return null

    setIsSubmitting(true)
    setError(null)
    try {
      const result = await createVocPost({
        title,
        content,
        status,
      })
      const newPost = result?.post
        ? { ...result.post, content: sanitizeContentHtml(result.post.content) }
        : null
      if (!newPost) throw new Error("글 등록에 실패했습니다.")

      setPosts((prev) => [newPost, ...prev])
      setSelectedPostId(newPost.id)
      setPagination((prev) => ({ ...prev, pageIndex: 0 }))
      resetForm()
      setIsCreateOpen(false)
      return newPost
    } catch (err) {
      setError(err?.message || "글 등록에 실패했습니다.")
      return null
    } finally {
      setIsSubmitting(false)
    }
  }, [form.content, form.title, resetForm])

  const deletePost = React.useCallback(
    async (postId) => {
      const target = posts.find((post) => post.id === postId)
      if (target && !canDeletePost(target)) {
        setError("작성자 또는 관리자만 삭제할 수 있습니다.")
        return
      }

      setError(null)
      try {
        await deleteVocPost(postId)
        setPosts((prev) => prev.filter((post) => post.id !== postId))
      } catch (err) {
        setError(err?.message || "게시글을 삭제하지 못했습니다.")
        return
      }

      if (selectedPostId === postId) {
        clearSelection()
      }
    },
    [canDeletePost, clearSelection, posts, selectedPostId],
  )

  const addReply = React.useCallback(
    async (postId) => {
      const replyText = (replyDrafts[postId] || "").trim()
      if (!replyText) return null

      setError(null)
      try {
        const result = await createVocReply({ postId, content: replyText })
        const updatedPost = result?.post
          ? { ...result.post, content: sanitizeContentHtml(result.post.content) }
          : null
        const reply = result?.reply
        setPosts((prev) =>
          prev.map((post) =>
            post.id === postId
              ? updatedPost || { ...post, replies: [...post.replies, reply].filter(Boolean) }
              : post,
          ),
        )
        setReplyDrafts((prev) => ({ ...prev, [postId]: "" }))
        return reply || null
      } catch (err) {
        setError(err?.message || "답변을 등록하지 못했습니다.")
        return null
      }
    },
    [replyDrafts],
  )

  const updateStatus = React.useCallback(async (postId, status) => {
    if (!status) return
    setError(null)
    try {
      const result = await updateVocPost(postId, { status })
      const updatedPost = result?.post
        ? { ...result.post, content: sanitizeContentHtml(result.post.content) }
        : null
      setPosts((prev) =>
        prev.map((post) =>
          post.id === postId ? updatedPost || { ...post, status } : post,
        ),
      )
    } catch (err) {
      setError(err?.message || "상태를 변경하지 못했습니다.")
    }
  }, [])

  const updatePost = React.useCallback(
    async (postId, updates = {}) => {
      const target = posts.find((post) => post.id === postId)
      if (target && !canDeletePost(target)) {
        setError("작성자 또는 관리자만 수정할 수 있습니다.")
        return null
      }

      const title = typeof updates.title === "string" ? updates.title.trim() : ""
      const content = sanitizeContentHtml(updates.content)
      if (!title || !hasMeaningfulContent(content, { skipSanitize: true })) {
        setError("제목과 내용을 입력해주세요.")
        return null
      }

      setError(null)
      setIsUpdating(true)
      try {
        const result = await updateVocPost(postId, { title, content })
        const updatedPost = result?.post
          ? { ...result.post, content: sanitizeContentHtml(result.post.content) }
          : null
        if (updatedPost) {
          setPosts((prev) => prev.map((post) => (post.id === postId ? updatedPost : post)))
        }
        return updatedPost
      } catch (err) {
        setError(err?.message || "게시글을 수정하지 못했습니다.")
        return null
      } finally {
        setIsUpdating(false)
      }
    },
    [canDeletePost, posts],
  )

  const selectPost = React.useCallback((postId) => {
    setSelectedPostId(postId)
    setIsDetailOpen(true)
  }, [])

  const updateReplyDraft = React.useCallback((postId, value) => {
    setReplyDrafts((prev) => ({ ...prev, [postId]: value }))
  }, [])

  const changePageSize = React.useCallback((nextSize) => {
    setPagination({ pageIndex: 0, pageSize: nextSize })
  }, [])

  const goToPage = React.useCallback(
    (pageIndex) => {
      setPagination((prev) => {
        const clamped = Math.min(
          Math.max(pageIndex, 0),
          Math.max(Math.ceil((filteredPosts.length || 1) / prev.pageSize) - 1, 0),
        )
        return { ...prev, pageIndex: clamped }
      })
    },
    [filteredPosts.length],
  )

  const nextPage = React.useCallback(() => {
    goToPage(pagination.pageIndex + 1)
  }, [goToPage, pagination.pageIndex])

  const prevPage = React.useCallback(() => {
    goToPage(pagination.pageIndex - 1)
  }, [goToPage, pagination.pageIndex])

  const firstPage = React.useCallback(() => {
    goToPage(0)
  }, [goToPage])

  const lastPage = React.useCallback(() => {
    goToPage(pageCount - 1)
  }, [goToPage, pageCount])

  return {
    statusCounts,
    statusFilter,
    filteredPosts,
    visiblePosts,
    pagination: {
      ...pagination,
      pageCount,
      currentPage,
      totalPages,
      totalRows: filteredPosts.length,
    },
    selectedPost,
    selectedPostId,
    clearSelection,
    isCreateOpen,
    setIsCreateOpen,
    isDetailOpen,
    setIsDetailOpen,
    replyDrafts,
    updateReplyDraft,
    form,
    updateForm,
    resetForm,
    createPost,
    deletePost,
    addReply,
    updateStatus,
    updatePost,
    selectPost,
    toggleStatusFilter,
    changePageSize,
    nextPage,
    prevPage,
    firstPage,
    lastPage,
    canDeletePost,
    isLoading,
    error,
    reload: loadPosts,
    isSubmitting,
    isUpdating,
  }
}
