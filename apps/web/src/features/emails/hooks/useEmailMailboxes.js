import { useQuery } from "@tanstack/react-query"

import { emailQueryKeys } from "../api/emailQueryKeys"
import { fetchEmailMailboxes } from "../api/emails"

export function useEmailMailboxes() {
  return useQuery({
    queryKey: emailQueryKeys.mailboxes,
    queryFn: () => fetchEmailMailboxes(),
    staleTime: 5 * 60 * 1000,
  })
}
