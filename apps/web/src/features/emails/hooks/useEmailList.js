import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchEmails } from "../api/emails"
import { normalizeEmailListFilters } from "../utils/filters"

export function useEmailList(filters, options = {}) {
  const enabled = typeof options.enabled === "boolean" ? options.enabled : true
  const normalized = normalizeEmailListFilters(filters)
  return useQuery({
    queryKey: emailQueryKeys.list(normalized),
    queryFn: () => fetchEmails(normalized),
    keepPreviousData: true,
    enabled,
  })
}
