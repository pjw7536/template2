import { useQuery } from "@tanstack/react-query"

import { fetchWorkHubContext } from "../api/workHub"

const workHubQueryKeys = {
  context: () => ["work-hub", "context"],
}

export function useWorkHubContext() {
  return useQuery({
    queryKey: workHubQueryKeys.context(),
    queryFn: fetchWorkHubContext,
    staleTime: 30_000,
    retry: 1,
  })
}
