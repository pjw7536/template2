import { useQuery } from "@tanstack/react-query"

import { lineDashboardQueryKeys } from "../api/query-keys"
import { getLineSdwtOptions } from "../api/get-line-sdwt-options"

export function useLineSdwtOptionsQuery(options = {}) {
  const { enabled = true } = options

  return useQuery({
    queryKey: lineDashboardQueryKeys.lineSdwtOptions(),
    queryFn: getLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}
