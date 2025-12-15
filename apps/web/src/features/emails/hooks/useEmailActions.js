import { useMutation, useQueryClient } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { bulkDeleteEmails, deleteEmail } from "../api/emails"

export function useDeleteEmail() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (emailId) => deleteEmail(emailId),
    onSuccess: (_data, emailId) => {
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.listPrefix })
      queryClient.removeQueries({ queryKey: emailQueryKeys.detail(emailId), exact: true })
      queryClient.removeQueries({ queryKey: emailQueryKeys.html(emailId), exact: true })
    },
  })
}

export function useBulkDeleteEmails() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (emailIds) => bulkDeleteEmails(emailIds),
    onSuccess: (_data, emailIds) => {
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.listPrefix })

      const safeEmailIds = Array.isArray(emailIds) ? emailIds : []
      const uniqueEmailIds = Array.from(new Set(safeEmailIds))

      uniqueEmailIds.forEach((emailId) => {
        queryClient.removeQueries({ queryKey: emailQueryKeys.detail(emailId), exact: true })
        queryClient.removeQueries({ queryKey: emailQueryKeys.html(emailId), exact: true })
      })
    },
  })
}
