import { useQuery } from "@tanstack/react-query"

import { getObserverLineSdwtOptions } from "../api/lineSdwtOptions"

export function useObserverLineSdwtOptions({ enabled = true } = {}) {
  return useQuery({
    queryKey: ["observer", "line-sdwt-options"],
    queryFn: getObserverLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}
