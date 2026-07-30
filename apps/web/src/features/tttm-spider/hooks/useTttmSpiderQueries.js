// 파일 경로: src/features/tttm-spider/hooks/useTttmSpiderQueries.js
import { useQuery } from "@tanstack/react-query"

import {
  fetchTttmChambers,
  fetchTttmEqps,
  fetchTttmComboOptions,
  fetchTttmDashboardData,
  fetchTttmGolden,
  fetchTttmLotwf,
  fetchTttmSensorTrace,
  tttmSpiderQueryKeys,
} from "../api"

// 전체 eqp 목록(자동완성용).
export function useTttmEqps() {
  return useQuery({
    queryKey: ["tttm-spider", "eqps"],
    queryFn: fetchTttmEqps,
    staleTime: 5 * 60 * 1000,
    select: (d) => d?.items ?? [],
  })
}

// eqp 의 chamber 목록(eqp만 입력하고 추가 시 전체 챔버).
export function useTttmChambers(eqp, enabled) {
  return useQuery({
    queryKey: ["tttm-spider", "chambers", eqp],
    queryFn: () => fetchTttmChambers(eqp),
    enabled: Boolean(enabled && eqp),
    staleTime: 60 * 1000,
    select: (d) => d?.items ?? [],
  })
}

// (eqp, chamber)에서 진행된 lotwf 목록.
export function useTttmLotwf(eqp, chamber, enabled) {
  return useQuery({
    queryKey: tttmSpiderQueryKeys.lotwf(eqp, chamber),
    queryFn: () => fetchTttmLotwf(eqp, chamber),
    enabled: Boolean(enabled && eqp && chamber),
    staleTime: 60 * 1000,
    select: (d) => d?.items ?? [],
  })
}

// 타설비검증 REF 후보(골든 챔버 lotwf).
export function useTttmGolden(recipe, enabled) {
  return useQuery({
    queryKey: tttmSpiderQueryKeys.golden(recipe),
    queryFn: () => fetchTttmGolden(recipe),
    enabled: Boolean(enabled),
    staleTime: 60 * 1000,
    select: (d) => d?.items ?? [],
  })
}

// line/eqp/chamber/date 캐스케이드 옵션. 상위 선택이 없으면 비활성.
export function useTttmComboOptions({ source, level, line, eqp, chamber, enabled = true }) {
  const parentKey = `${line || ""}|${eqp || ""}|${chamber || ""}`
  return useQuery({
    queryKey: tttmSpiderQueryKeys.comboOptions(source, level, parentKey),
    queryFn: () => fetchTttmComboOptions({ source, level, line, eqp, chamber }),
    enabled,
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
    select: (data) => data?.items ?? [],
  })
}

// scores.parquet → 대시보드 번들. payload 가 준비됐을 때만 호출.
export function useTttmDashboardData(payload, selectionKey, enabled) {
  return useQuery({
    queryKey: tttmSpiderQueryKeys.dashboardData(selectionKey),
    queryFn: () => fetchTttmDashboardData(payload),
    enabled: Boolean(enabled && payload),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
    retry: false,
  })
}

// 센서(또는 OES step) 드릴다운 원파형/decomp.
export function useTttmSensorTrace(payload, traceKey, enabled) {
  return useQuery({
    queryKey: tttmSpiderQueryKeys.sensorTrace(traceKey),
    queryFn: () => fetchTttmSensorTrace(payload),
    enabled: Boolean(enabled && payload),
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
    retry: false,
  })
}
