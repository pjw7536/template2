import { useQuery } from "@tanstack/react-query"
import { fetchEmails } from "../api/emails"

export function useEmailList(filters, options = {}) {
  const enabled = typeof options.enabled === "boolean" ? options.enabled : true
  return useQuery({
    queryKey: ["emails", filters],
    queryFn: () => fetchEmails(filters),
    keepPreviousData: true,
    enabled,
  })
}
