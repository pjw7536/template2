// src/features/voc/hooks/useQnaBoardState.js
// Q&A 게시판 상태/동작을 캡슐화한 훅 (React Query 기반 데이터 소스)
import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { DEFAULT_STATUS, STATUS_OPTIONS } from "../constants"
import { vocQueryKeys } from "../api/query-keys"
import {
  createVocPost,
  createVocReply,
  deleteVocPost,
  fetchVocPosts,
  updateVocPost,
} from "../api/voc"
import { hasMeaningfulContent, sanitizeContentHtml } from "../utils"

const EMPTY_STATUS_COUNTS = STATUS_OPTIONS.reduce(
  (acc, option) => ({ ...acc, [option.value]: 0 }),
  {},
)

function sanitizePost(post) {
  if (!post || post.id == null) return null
  return {
    ...post,
    content: sanitizeContentHtml(post.content),
    replies: Array.isArray(post.replies)
      ? post.replies
          .map((reply) => {
            if (!reply || reply.id == null) return null
            return {
              ...reply,
              content: typeof reply.content === "string" ? reply.content.trim() : "",
            }
          })
          .filter(Boolean)
      : [],
  }
}

function normalizePosts(rawPosts) {
  if (!Array.isArray(rawPosts)) return []
  return rawPosts.map(sanitizePost).filter(Boolean)
}

function buildStatusCounts(posts, providedCounts) {
  if (providedCounts && typeof providedCounts === "object") {
    return { ...EMPTY_STATUS_COUNTS, ...providedCounts }
  }

  return posts.reduce((acc, post) => {
    if (post?.status && typeof acc[post.status] === "number") {
      acc[post.status] += 1
    }
    return acc
  }, { ...EMPTY_STATUS_COUNTS })
}

export function useQnaBoardState({ currentUser, isAdmin }) {
  const queryClient = useQueryClient()

  const [statusFilter, setStatusFilter] = React.useState(null)
  const [form, setForm] = React.useState({ title: "", content: "" })
  const [replyDrafts, setReplyDrafts] = React.useState({})
  const [selectedPostId, setSelectedPostId] = React.useState(null)
  const [isCreateOpen, setIsCreateOpen] = React.useState(false)
  const [pagination, setPagination] = React.useState({ pageIndex: 0, pageSize: 8 })
  const [isDetailOpen, setIsDetailOpen] = React.useState(false)
  const [error, setError] = React.useState(null)

  const postsQuery = useQuery({
    queryKey: vocQueryKeys.posts(),
    queryFn: fetchVocPosts,
    select: (payload) => {
      const posts = normalizePosts(payload?.posts)
      return {
        posts,
        statusCounts: buildStatusCounts(posts, payload?.statusCounts),
      }
    },
  })

  React.useEffect(() => {
    if (postsQuery.error) {
      setError(postsQuery.error?.message || "VOC 데이터를 불러오지 못했습니다.")
    }
  }, [postsQuery.error])

  React.useEffect(() => {
    if (postsQuery.isSuccess) {
      setError(null)
    }
  }, [postsQuery.isSuccess])

  const posts = postsQuery.data?.posts ?? []
  const statusCounts = postsQuery.data?.statusCounts ?? buildStatusCounts(posts)

  const filteredPosts = statusFilter ? posts.filter((post) => post.status === statusFilter) : posts
  const start = pagination.pageIndex * pagination.pageSize
  const end = start + pagination.pageSize
  const visiblePosts = filteredPosts.slice(start, end)

  const pageCount = Math.max(Math.ceil(Math.max(filteredPosts.length, 1) / pagination.pageSize), 1)
  const currentPage = pagination.pageIndex + 1
  const totalPages = pageCount

  const selectedPost = posts.find((post) => post.id === selectedPostId) || null
  const isRefreshing = postsQuery.isFetching && !postsQuery.isPending

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
      Math.ceil(Math.max(filteredPosts.length, 1) / pagination.pageSize) - 1,
      0,
    )
    if (pagination.pageIndex > lastPageIndex) {
      setPagination((prev) => ({ ...prev, pageIndex: lastPageIndex }))
    }
  }, [filteredPosts.length, pagination.pageIndex, pagination.pageSize])

  const updateForm = (key, valueOrUpdater) => {
    setForm((prev) => {
      const nextValue =
        typeof valueOrUpdater === "function" ? valueOrUpdater(prev[key]) : valueOrUpdater
      return { ...prev, [key]: nextValue }
    })
  }

  const resetForm = () => {
    setForm({ title: "", content: "" })
  }

  const clearSelection = () => {
    setSelectedPostId(null)
    setIsDetailOpen(false)
  }

  const canDeletePost = (post) => {
    if (isAdmin) return true
    const authorKey = post.author?.id || post.author?.email || post.author?.name
    return Boolean(authorKey && authorKey === currentUser.id)
  }

  const toggleStatusFilter = (status) => {
    setStatusFilter((prev) => (prev === status ? null : status))
    setPagination((prev) => ({ ...prev, pageIndex: 0 }))
  }

  const updatePostsCache = (updater, nextStatusCounts) => {
    queryClient.setQueryData(vocQueryKeys.posts(), (previous) => {
      const base = previous?.posts ?? posts
      const updated = normalizePosts(updater(base))
      const countsSource =
        nextStatusCounts && typeof nextStatusCounts === "object" ? nextStatusCounts : undefined
      return {
        posts: updated,
        statusCounts: buildStatusCounts(updated, countsSource),
      }
    })
  }

  const createPostMutation = useMutation({
    mutationFn: ({ title, content, status }) => createVocPost({ title, content, status }),
    onMutate: () => {
      setError(null)
    },
    onError: (err) => {
      setError(err?.message || "글 등록에 실패했습니다.")
    },
    onSuccess: (result) => {
      if (!result?.post) return
      const safePost = sanitizePost(result.post)
      if (!safePost) return

      updatePostsCache((prev) => [safePost, ...(prev ?? [])], result.statusCounts)
      setSelectedPostId(safePost.id)
      setPagination((prev) => ({ ...prev, pageIndex: 0 }))
      resetForm()
      setIsCreateOpen(false)
    },
  })

  const deletePostMutation = useMutation({
    mutationFn: (postId) => deleteVocPost(postId),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "게시글을 삭제하지 못했습니다.")
    },
    onSuccess: (result, postId) => {
      updatePostsCache(
        (prev) => (prev ?? []).filter((post) => post.id !== postId),
        result?.statusCounts,
      )
      if (selectedPostId === postId) {
        clearSelection()
      }
    },
  })

  const updatePostMutation = useMutation({
    mutationFn: ({ postId, updates }) => updateVocPost(postId, updates),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "게시글을 수정하지 못했습니다.")
    },
    onSuccess: (result) => {
      if (!result?.post) return
      const safePost = sanitizePost(result.post)
      if (!safePost) return

      updatePostsCache(
        (prev) => (prev ?? []).map((post) => (post.id === safePost.id ? safePost : post)),
        result.statusCounts,
      )
    },
  })

  const replyMutation = useMutation({
    mutationFn: ({ postId, content }) => createVocReply({ postId, content }),
    onMutate: () => setError(null),
    onError: (err) => {
      setError(err?.message || "답변을 등록하지 못했습니다.")
    },
    onSuccess: (result, variables) => {
      const reply = result?.reply
      const safePost = sanitizePost(result?.post)
      if (!reply && !safePost) return
      const targetId = variables.postId

      updatePostsCache((prev) =>
        (prev ?? []).map((post) => {
          if (post.id !== targetId) return post
          if (safePost) return safePost
          return { ...post, replies: [...post.replies, reply].filter(Boolean) }
        }),
      )
      setReplyDrafts((prev) => ({ ...prev, [targetId]: "" }))
    },
  })

  const createPost = async () => {
    const title = form.title.trim()
    const content = sanitizeContentHtml(form.content)
    const status = DEFAULT_STATUS

    if (!title || !hasMeaningfulContent(content, { skipSanitize: true }) || !status) return null
    try {
      const result = await createPostMutation.mutateAsync({ title, content, status })
      return result?.post ? sanitizePost(result.post) : null
    } catch {
      return null
    }
  }

  const deletePost = async (postId) => {
    const target = posts.find((post) => post.id === postId)
    if (target && !canDeletePost(target)) {
      setError("작성자 또는 관리자만 삭제할 수 있습니다.")
      return
    }
    try {
      await deletePostMutation.mutateAsync(postId)
    } catch {
      // mutateAsync already sets error message
    }
  }

  const addReply = async (postId) => {
    const replyText = (replyDrafts[postId] || "").trim()
    if (!replyText) return null
    try {
      await replyMutation.mutateAsync({ postId, content: replyText })
    } catch {
      return null
    }
    return null
  }

  const updateStatus = async (postId, status) => {
    if (!status) return
    try {
      await updatePostMutation.mutateAsync({ postId, updates: { status } })
    } catch {
      // handled by mutation onError
    }
  }

  const updatePost = async (postId, updates = {}) => {
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

    try {
      const result = await updatePostMutation.mutateAsync({
        postId,
        updates: { title, content },
      })
      return result?.post ? sanitizePost(result.post) : null
    } catch {
      return null
    }
  }

  const selectPost = (postId) => {
    setSelectedPostId(postId)
    setIsDetailOpen(true)
  }

  const updateReplyDraft = (postId, value) => {
    setReplyDrafts((prev) => ({ ...prev, [postId]: value }))
  }

  const changePageSize = (nextSize) => {
    setPagination({ pageIndex: 0, pageSize: nextSize })
  }

  const goToPage = (pageIndex) => {
    setPagination((prev) => {
      const clamped = Math.min(
        Math.max(pageIndex, 0),
        Math.max(Math.ceil(Math.max(filteredPosts.length, 1) / prev.pageSize) - 1, 0),
      )
      return { ...prev, pageIndex: clamped }
    })
  }

  const nextPage = () => {
    goToPage(pagination.pageIndex + 1)
  }

  const prevPage = () => {
    goToPage(pagination.pageIndex - 1)
  }

  const firstPage = () => {
    goToPage(0)
  }

  const lastPage = () => {
    goToPage(pageCount - 1)
  }

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
    isLoading: postsQuery.isPending,
    isRefreshing,
    error,
    reload: postsQuery.refetch,
    isSubmitting: createPostMutation.isPending,
    isUpdating: updatePostMutation.isPending,
    isReplying: replyMutation.isPending,
  }
}
