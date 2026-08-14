import { useQuery } from "@tanstack/react-query"

import { getLineSdwtOptions } from "../api/lineSdwtOptions"

const LINE_SDWT_OPTIONS_QUERY_KEY = ["affiliation", "line-sdwt-options"]

function toLineOptions(payload) {
  return Array.from(
    new Set(
      (Array.isArray(payload?.lines) ? payload.lines : [])
        .map((line) => (typeof line?.lineId === "string" ? line.lineId.trim() : ""))
        .filter(Boolean),
    ),
  )
}

export function useLineSdwtOptionsQuery({ enabled = true } = {}) {
  return useQuery({
    queryKey: LINE_SDWT_OPTIONS_QUERY_KEY,
    queryFn: getLineSdwtOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}

export function useLineOptionsQuery({ enabled = true } = {}) {
  return useQuery({
    queryKey: LINE_SDWT_OPTIONS_QUERY_KEY,
    queryFn: getLineSdwtOptions,
    select: toLineOptions,
    refetchOnWindowFocus: false,
    enabled,
  })
}
