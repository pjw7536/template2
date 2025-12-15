import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchEmail, fetchEmailHtml } from "../api/emails"

export function useEmailDetail(emailId) {
  return useQuery({
    queryKey: emailQueryKeys.detail(emailId),
    queryFn: () => fetchEmail(emailId),
    enabled: Boolean(emailId),
  })
}

export function useEmailHtml(emailId) {
  return useQuery({
    queryKey: emailQueryKeys.html(emailId),
    queryFn: () => fetchEmailHtml(emailId),
    enabled: Boolean(emailId),
    staleTime: 5 * 60 * 1000,
  })
}
