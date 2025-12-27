import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchInboxEmails, fetchSentEmails } from "../api/emails"
import { normalizeEmailListFilters } from "../utils/filters"

export function useEmailList(filters, options = {}) {
  const enabled = typeof options.enabled === "boolean" ? options.enabled : true
  const normalized = normalizeEmailListFilters(filters)
  const scope = normalized.scope === "sent" ? "sent" : "inbox"
  const fetcher = scope === "sent" ? fetchSentEmails : fetchInboxEmails
  return useQuery({
    queryKey: emailQueryKeys.list(normalized),
    queryFn: () => fetcher(normalized),
    keepPreviousData: true,
    enabled,
  })
}
