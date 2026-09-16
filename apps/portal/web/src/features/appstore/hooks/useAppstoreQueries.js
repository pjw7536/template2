// 파일 경로: src/features/appstore/hooks/useAppstoreQueries.js
// Appstore 전용 React Query 훅 모음

import { useQuery } from "@tanstack/react-query"

import { fetchApp, fetchApps, fetchComments } from "../api/appstore"
import { appstoreQueryKeys } from "../api/queryKeys"

export function useAppsQuery() {
  return useQuery({
    queryKey: appstoreQueryKeys.apps(),
    queryFn: fetchApps,
  })
}

export function useAppDetailQuery(appId, options = {}) {
  return useQuery({
    queryKey: appstoreQueryKeys.app(appId),
    queryFn: () => fetchApp(appId),
    enabled: Boolean(appId),
    ...options,
  })
}

export function useAppCommentsQuery(appId, options = {}) {
  return useQuery({
    queryKey: appstoreQueryKeys.comments(appId),
    queryFn: () => fetchComments(appId),
    enabled: Boolean(appId),
    ...options,
  })
}
