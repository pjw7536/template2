// src/features/appstore/hooks/useAppstoreMutations.js
// Appstore 전용 React Query mutation 훅

import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  createApp,
  createComment,
  deleteApp,
  deleteComment,
  incrementView,
  toggleLike,
  updateApp,
  updateComment,
} from "../api/appstore"
import { appstoreQueryKeys } from "../api/query-keys"

function updateList(queryClient, updater) {
  queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
    if (!previous || !Array.isArray(previous.apps)) return previous
    const nextApps = updater(previous.apps)
    return {
      ...previous,
      apps: nextApps,
      total: typeof previous.total === "number" ? previous.total : nextApps.length,
    }
  })
}

function updateDetail(queryClient, appId, updater) {
  queryClient.setQueryData(appstoreQueryKeys.app(appId), (previous) => {
    if (!previous?.app) return previous
    const nextApp = updater(previous.app)
    return { app: nextApp }
  })
}

export function useAppstoreMutations() {
  const queryClient = useQueryClient()

  const createAppMutation = useMutation({
    mutationFn: createApp,
    onSuccess: (app) => {
      queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
        const prevApps = previous?.apps ?? []
        const nextApps = [app, ...prevApps.filter((item) => item.id !== app.id)]
        const prevTotal =
          typeof previous?.total === "number" ? previous.total : prevApps.length
        return { apps: nextApps, total: prevTotal + 1 }
      })
      queryClient.setQueryData(appstoreQueryKeys.app(app.id), { app })
    },
  })

  const updateAppMutation = useMutation({
    mutationFn: ({ appId, updates }) => updateApp(appId, updates),
    onSuccess: (app) => {
      updateList(queryClient, (apps) =>
        apps.map((item) => (item.id === app.id ? { ...item, ...app } : item)),
      )
      queryClient.setQueryData(appstoreQueryKeys.app(app.id), { app })
    },
  })

  const deleteAppMutation = useMutation({
    mutationFn: (appId) => deleteApp(appId),
    onSuccess: (_result, appId) => {
      queryClient.setQueryData(appstoreQueryKeys.apps(), (previous) => {
        if (!previous?.apps) return previous
        const filtered = previous.apps.filter((item) => item.id !== appId)
        const prevTotal =
          typeof previous.total === "number" ? previous.total : previous.apps.length
        return { apps: filtered, total: Math.max(prevTotal - 1, filtered.length) }
      })
      queryClient.removeQueries({ queryKey: appstoreQueryKeys.app(appId) })
      queryClient.removeQueries({ queryKey: appstoreQueryKeys.comments(appId) })
    },
  })

  const toggleLikeMutation = useMutation({
    mutationFn: (appId) => toggleLike(appId),
    onSuccess: (result) => {
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === result.appId
            ? { ...item, liked: result.liked, likeCount: result.likeCount }
            : item,
        ),
      )
      updateDetail(queryClient, result.appId, (app) => ({
        ...app,
        liked: result.liked,
        likeCount: result.likeCount,
      }))
    },
  })

  const viewMutation = useMutation({
    mutationFn: (appId) => incrementView(appId),
    onSuccess: (result) => {
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === result.appId ? { ...item, viewCount: result.viewCount } : item,
        ),
      )
      updateDetail(queryClient, result.appId, (app) => ({
        ...app,
        viewCount: result.viewCount,
      }))
    },
  })

  const createCommentMutation = useMutation({
    mutationFn: ({ appId, content }) => createComment(appId, content),
    onSuccess: (comment, variables) => {
      updateDetail(queryClient, variables.appId, (app) => {
        const nextComments = [...(app.comments ?? []), comment]
        return { ...app, comments: nextComments, commentCount: nextComments.length }
      })
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === variables.appId
            ? { ...item, commentCount: (item.commentCount ?? 0) + 1 }
            : item,
        ),
      )
      queryClient.setQueryData(appstoreQueryKeys.comments(variables.appId), (previous) => {
        if (!previous?.comments) return previous
        return {
          ...previous,
          comments: [...previous.comments, comment],
          total: (previous.total ?? previous.comments.length) + 1,
        }
      })
    },
  })

  const updateCommentMutation = useMutation({
    mutationFn: ({ appId, commentId, content }) => updateComment(appId, commentId, content),
    onSuccess: (comment, variables) => {
      updateDetail(queryClient, variables.appId, (app) => {
        const nextComments = (app.comments ?? []).map((item) =>
          item.id === comment.id ? comment : item,
        )
        return { ...app, comments: nextComments }
      })
      queryClient.setQueryData(appstoreQueryKeys.comments(variables.appId), (previous) => {
        if (!previous?.comments) return previous
        return {
          ...previous,
          comments: previous.comments.map((item) => (item.id === comment.id ? comment : item)),
        }
      })
    },
  })

  const deleteCommentMutation = useMutation({
    mutationFn: ({ appId, commentId }) => deleteComment(appId, commentId),
    onSuccess: (_result, variables) => {
      updateDetail(queryClient, variables.appId, (app) => {
        const nextComments = (app.comments ?? []).filter((item) => item.id !== variables.commentId)
        return { ...app, comments: nextComments, commentCount: nextComments.length }
      })
      updateList(queryClient, (apps) =>
        apps.map((item) =>
          item.id === variables.appId
            ? { ...item, commentCount: Math.max((item.commentCount ?? 1) - 1, 0) }
            : item,
        ),
      )
      queryClient.setQueryData(appstoreQueryKeys.comments(variables.appId), (previous) => {
        if (!previous?.comments) return previous
        const filtered = previous.comments.filter((item) => item.id !== variables.commentId)
        return {
          ...previous,
          comments: filtered,
          total: Math.max((previous.total ?? filtered.length) - 1, filtered.length),
        }
      })
    },
  })

  return {
    createAppMutation,
    updateAppMutation,
    deleteAppMutation,
    toggleLikeMutation,
    viewMutation,
    createCommentMutation,
    updateCommentMutation,
    deleteCommentMutation,
  }
}
