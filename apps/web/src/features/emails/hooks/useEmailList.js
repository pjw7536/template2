import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchEmails } from "../api/emails"

export function useEmailList(filters, options = {}) {
  const enabled = typeof options.enabled === "boolean" ? options.enabled : true
  return useQuery({
    queryKey: emailQueryKeys.list(filters),
    queryFn: () => fetchEmails(filters),
    keepPreviousData: true,
    enabled,
  })
}
