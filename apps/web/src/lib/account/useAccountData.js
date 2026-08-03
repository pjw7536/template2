import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { accountApi } from "./accountApi"
import { normalizeAccountOverview } from "./accountOverview"
import {
  withDevAccessAuditFixtures,
  withDevPendingAccessUserFixtures,
} from "./devFixtures"

export const AFFILIATION_QUERY_KEY = ["account", "affiliation"]
const AFFILIATION_REQUESTS_QUERY_KEY = ["account", "affiliationRequests"]
const AFFILIATION_MEMBERS_QUERY_KEY = ["account", "affiliationMembers"]
const AFFILIATION_GRANT_CANDIDATES_QUERY_KEY = ["account", "affiliationGrantCandidates"]
const OVERVIEW_QUERY_KEY = ["account", "overview"]
const ACCESS_USERS_QUERY_KEY = ["account", "accessUsers"]
const PENDING_ACCESS_REQUESTS_QUERY_KEY = ["account", "pendingAccessRequests"]
const ACCESS_MATRIX_QUERY_KEY = ["account", "accessMatrix"]
const ACCESS_POLICY_RULES_QUERY_KEY = ["account", "accessPolicyRules"]
const ACCESS_AUDIT_LOGS_QUERY_KEY = ["account", "accessAuditLogs"]
const USER_SCOPE_DATA_QUERY_KEY = ["account", "userScopeData"]

function replaceAccessMatrixRow(data, matrixRow) {
  const userId = matrixRow?.user?.id
  if (!data?.pages || !userId) return data

  for (let pageIndex = 0; pageIndex < data.pages.length; pageIndex += 1) {
    const page = data.pages[pageIndex]
    const results = page?.results || []
    const rowIndex = results.findIndex((row) => row?.user?.id === userId)
    if (rowIndex < 0) continue

    const pages = [...data.pages]
    const nextResults = [...results]
    nextResults[rowIndex] = matrixRow
    pages[pageIndex] = { ...page, results: nextResults }
    return { ...data, pages }
  }
  return data
}

function refreshAccessDecisionQueries({ queryClient, refreshAuth, matrixRow }) {
  const refreshTasks = [
    refreshAuth(),
    queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
    queryClient.invalidateQueries({ queryKey: PENDING_ACCESS_REQUESTS_QUERY_KEY }),
    queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
    queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY }),
  ]

  if (matrixRow) {
    queryClient.setQueriesData(
      {
        queryKey: ACCESS_MATRIX_QUERY_KEY,
        predicate: (query) => query.queryKey[6] !== true,
      },
      (data) => replaceAccessMatrixRow(data, matrixRow),
    )
    refreshTasks.push(
      queryClient.invalidateQueries({
        queryKey: ACCESS_MATRIX_QUERY_KEY,
        predicate: (query) => query.queryKey[6] === true,
      }),
    )
  } else {
    refreshTasks.push(
      queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
    )
  }

  void Promise.allSettled(refreshTasks)
}

export function useAffiliation() {
  return useQuery({
    queryKey: AFFILIATION_QUERY_KEY,
    queryFn: accountApi.fetchAffiliation,
  })
}

export function useUpdateAffiliation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateAffiliation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY })
    },
  })
}

export function useAccountOverview({ enabled = true } = {}) {
  return useQuery({
    queryKey: OVERVIEW_QUERY_KEY,
    queryFn: accountApi.fetchOverview,
    select: normalizeAccountOverview,
    enabled,
  })
}

export function useInfiniteAffiliationRequests({
  pageSize = 20,
  status = "pending",
  search = "",
  userSdwtProd = "",
} = {}) {
  return useInfiniteQuery({
    queryKey: [
      ...AFFILIATION_REQUESTS_QUERY_KEY,
      "infinite",
      pageSize,
      status,
      search,
      userSdwtProd,
    ],
    queryFn: ({ pageParam = 1 }) =>
      accountApi.fetchAffiliationRequests({
        page: pageParam,
        pageSize,
        status,
        search,
        userSdwtProd,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const currentPage = Number(lastPage?.page) || 1
      const totalPages = Number(lastPage?.totalPages) || 1
      return currentPage < totalPages ? currentPage + 1 : undefined
    },
    enabled: Boolean(userSdwtProd),
  })
}

export function useAffiliationMembers({ userSdwtProd } = {}) {
  return useQuery({
    queryKey: [...AFFILIATION_MEMBERS_QUERY_KEY, userSdwtProd],
    queryFn: () => accountApi.fetchAffiliationMembers({ userSdwtProd }),
    enabled: Boolean(userSdwtProd),
  })
}

export function useAffiliationDecision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.decideAffiliationRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AFFILIATION_REQUESTS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: AFFILIATION_MEMBERS_QUERY_KEY })
    },
  })
}

export function useAffiliationGrantCandidates({ search = "", enabled = true } = {}) {
  return useQuery({
    queryKey: [...AFFILIATION_GRANT_CANDIDATES_QUERY_KEY, search],
    queryFn: () => accountApi.fetchUserPool({ search, limit: 50 }),
    enabled,
  })
}

export function useAffiliationAccessMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ action = "grant", ...payload }) =>
      action === "revoke"
        ? accountApi.revokeAffiliationAccess(payload)
        : accountApi.grantAffiliationAccess(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AFFILIATION_MEMBERS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY })
    },
  })
}

export function useAccessUsers({
  page = 1,
  pageSize = 20,
  status = "",
  source = "",
  search = "",
  department = "",
  scope = "portal",
  enabled = true,
} = {}) {
  return useQuery({
    queryKey: [
      ...ACCESS_USERS_QUERY_KEY,
      page,
      pageSize,
      status,
      source,
      search,
      department,
      scope,
    ],
    queryFn: () =>
      accountApi.fetchAccessUsers({
        page,
        pageSize,
        status,
        source,
        search,
        department,
        scope,
      }),
    select: (data) => withDevPendingAccessUserFixtures(data, { page, pageSize, status }),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useAccessMatrix({
  pageSize = 20,
  search = "",
  department = "",
  manualGrantOnly = false,
  enabled = true,
} = {}) {
  return useInfiniteQuery({
    queryKey: [
      ...ACCESS_MATRIX_QUERY_KEY,
      "infinite",
      pageSize,
      search,
      department,
      manualGrantOnly,
    ],
    queryFn: ({ pageParam = 1 }) => accountApi.fetchAccessMatrix({
      page: pageParam,
      pageSize,
      search,
      department,
      manualGrantOnly,
    }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const currentPage = Number(lastPage?.pagination?.page) || 1
      const totalPages = Number(lastPage?.pagination?.totalPages) || 1
      return currentPage < totalPages ? currentPage + 1 : undefined
    },
    select: (data) => {
      const pages = data?.pages || []
      const firstPage = pages[0] || {}
      const lastPage = pages[pages.length - 1] || firstPage
      return {
        ...data,
        scopes: firstPage.scopes || [],
        results: pages.flatMap((pageData) => pageData?.results || []),
        pagination: lastPage.pagination || firstPage.pagination || {},
      }
    },
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function usePendingAccessRequests({
  pageSize = 20,
  scope = "all",
  enabled = true,
} = {}) {
  return useInfiniteQuery({
    queryKey: [
      ...PENDING_ACCESS_REQUESTS_QUERY_KEY,
      "infinite",
      pageSize,
      scope,
    ],
    queryFn: ({ pageParam = 1 }) =>
      accountApi.fetchPendingAccessRequests({
        page: pageParam,
        pageSize,
        scope,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const currentPage = Number(lastPage?.pagination?.page) || 1
      const totalPages = Number(lastPage?.pagination?.totalPages) || 1
      return currentPage < totalPages ? currentPage + 1 : undefined
    },
    select: (data) => {
      const pages = data?.pages || []
      const firstPage = pages[0] || {}
      const lastPage = pages[pages.length - 1] || firstPage
      return {
        ...data,
        results: pages.flatMap((pageData) => pageData?.results || []),
        scopeCounts: firstPage.scopeCounts || [],
        summary: firstPage.summary || { total: 0 },
        pagination: lastPage.pagination || firstPage.pagination || {},
      }
    },
    enabled,
  })
}

export function useBulkApprovePendingAccessRequests({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.bulkApprovePendingAccessRequests,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: PENDING_ACCESS_REQUESTS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: OVERVIEW_QUERY_KEY }),
      ])
    },
  })
}

export function useAccessUserDecision({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.decideAccessUser,
    onSuccess: (data) => {
      refreshAccessDecisionQueries({
        queryClient,
        refreshAuth,
        matrixRow: data?.matrixRow,
      })
    },
  })
}

export function useUserScopeData({ userId, scope, enabled = true } = {}) {
  return useQuery({
    queryKey: [...USER_SCOPE_DATA_QUERY_KEY, userId, scope],
    queryFn: () => accountApi.fetchUserScopeData({ userId, scope }),
    enabled: Boolean(enabled && userId && scope),
  })
}

export function useUpdateUserScopeData() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateUserScopeData,
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: [
            ...USER_SCOPE_DATA_QUERY_KEY,
            variables.userId,
            variables.scope,
          ],
        }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useApplyAllUserAccess({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.applyAllAccessUser,
    onSuccess: (data) => {
      refreshAccessDecisionQueries({
        queryClient,
        refreshAuth,
        matrixRow: data?.matrixRow,
      })
    },
  })
}

export function useAccessPolicyRules({ scope = "portal", enabled = true } = {}) {
  return useQuery({
    queryKey: [...ACCESS_POLICY_RULES_QUERY_KEY, scope],
    queryFn: () => accountApi.fetchAccessPolicyRules({ scope }),
    enabled,
  })
}

export function useCreateAccessPolicyRule({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.createAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useBulkApplyAccessPolicyRules({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.bulkApplyAccessPolicyRules,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useUpdateAccessPolicyRule({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useDeleteAccessPolicyRule({ refreshAuth }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.deleteAccessPolicyRule,
    onSuccess: async () => {
      await Promise.all([
        refreshAuth(),
        queryClient.invalidateQueries({ queryKey: ACCESS_POLICY_RULES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_MATRIX_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_USERS_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: ACCESS_AUDIT_LOGS_QUERY_KEY }),
      ])
    },
  })
}

export function useAccessAuditLogs({
  page = 1,
  pageSize = 20,
  scope = "",
  userId = "",
  action = "",
  enabled = true,
} = {}) {
  return useQuery({
    queryKey: [...ACCESS_AUDIT_LOGS_QUERY_KEY, page, pageSize, scope, userId, action],
    queryFn: () =>
      accountApi.fetchAccessAuditLogs({
        page,
        pageSize,
        scope,
        userId,
        action,
      }),
    select: (data) => withDevAccessAuditFixtures(data, { page, pageSize }),
    placeholderData: keepPreviousData,
    enabled,
  })
}
