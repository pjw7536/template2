import { useQuery } from "@tanstack/react-query";
import { timelineApi } from "../api/timelineApi";

// ① 라인 목록 (언제나 요청)
export const useLines = () =>
  useQuery({
    queryKey: ["timeline", "lines"],
    queryFn: timelineApi.fetchLines,
    staleTime: 1000 * 60 * 30,
  });

// ② SDWT 목록 (lineId 가 있어야 동작)
export const useSDWT = (lineId) =>
  useQuery({
    queryKey: ["timeline", "sdwts", lineId],
    queryFn: () => timelineApi.fetchSDWT(lineId),
    enabled: !!lineId,
    staleTime: 1000 * 60 * 30,
  });

// ③ PRC Group 목록 (lineId와 sdwtId가 있어야 동작)
export const usePrcGroups = (lineId, sdwtId) =>
  useQuery({
    queryKey: ["timeline", "prcGroups", lineId, sdwtId],
    queryFn: () => timelineApi.fetchPrcGroups(lineId, sdwtId),
    enabled: !!lineId && !!sdwtId,
    staleTime: 1000 * 60 * 30,
  });

// ④ EQP 목록 (line + sdwt + prcGroup 모두 골랐을 때만)
export const useEquipments = (lineId, sdwtId, prcGroup) =>
  useQuery({
    queryKey: ["timeline", "equipments", lineId, sdwtId, prcGroup],
    queryFn: () => timelineApi.fetchEquipments(lineId, sdwtId, prcGroup),
    enabled: !!lineId && !!sdwtId && !!prcGroup,
    staleTime: 1000 * 60 * 30,
  });
