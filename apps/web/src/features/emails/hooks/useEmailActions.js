import { useMutation, useQueryClient } from "@tanstack/react-query"
import { bulkDeleteEmails, deleteEmail } from "../api/emails"

export function useDeleteEmail() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (emailId) => deleteEmail(emailId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["emails"] })
      queryClient.invalidateQueries({ queryKey: ["email"] })
    },
  })
}

export function useBulkDeleteEmails() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (emailIds) => bulkDeleteEmails(emailIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["emails"] })
      queryClient.invalidateQueries({ queryKey: ["email"] })
    },
  })
}
