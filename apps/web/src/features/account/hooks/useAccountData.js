import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { accountApi } from "../api/accountApi"

export const AFFILIATION_QUERY_KEY = ["account", "affiliation"]
export const MANAGEABLE_QUERY_KEY = ["account", "manageable"]

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
    },
  })
}

export function useManageableGroups() {
  return useQuery({
    queryKey: MANAGEABLE_QUERY_KEY,
    queryFn: accountApi.fetchManageableGroups,
  })
}

export function useUpdateGrant() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: accountApi.updateGrant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MANAGEABLE_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: AFFILIATION_QUERY_KEY })
    },
  })
}
