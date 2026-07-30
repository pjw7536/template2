// 파일 경로: src/features/tttm-spider/api/queryKeys.js
// TTTM Spider React Query 키 정의

export const tttmSpiderQueryKeys = {
  all: ["tttm-spider"],
  comboOptions: (source, level, parentKey) => ["tttm-spider", "combo", source, level, parentKey],
  dashboardData: (selectionKey) => ["tttm-spider", "dashboard-data", selectionKey],
  sensorTrace: (traceKey) => ["tttm-spider", "sensor-trace", traceKey],
  lotwf: (eqp, chamber) => ["tttm-spider", "lotwf", eqp, chamber],
  golden: (recipe) => ["tttm-spider", "golden", recipe || ""],
}
