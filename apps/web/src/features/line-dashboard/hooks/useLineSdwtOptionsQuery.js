import { useQuery } from "@tanstack/react-query"

import { lineDashboardQueryKeys } from "../api/queryKeys"
import { getLineSdwtOptions } from "../api/getLineSdwtOptions"

export function useLineSdwtOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: lineDashboardQueryKeys.lineSdwtOptions(),
    queryFn: getLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}
