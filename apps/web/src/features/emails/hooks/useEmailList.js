import { useQuery } from "@tanstack/react-query"
import { fetchEmails } from "../api/emails"

export function useEmailList(filters) {
  return useQuery({
    queryKey: ["emails", filters],
    queryFn: () => fetchEmails(filters),
    keepPreviousData: true,
  })
}
