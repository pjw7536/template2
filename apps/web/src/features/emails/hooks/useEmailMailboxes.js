import { useQuery } from "@tanstack/react-query"

import { fetchEmailMailboxes } from "../api/emails"

export function useEmailMailboxes() {
  return useQuery({
    queryKey: ["emails", "mailboxes"],
    queryFn: () => fetchEmailMailboxes(),
    staleTime: 5 * 60 * 1000,
  })
}

