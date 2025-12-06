// src/features/timeline/utils/tipUtils.js 그룹키 생성

export function getTipGroupKey(log) {
  return `${log.lineId || "UNKNOWN_LINE"}_${log.process || "unknown"}_${
    log.step || "unknown"
  }_${log.ppid || "unknown"}`;
}
