// src/features/line-dashboard/utils/statusLabels.js
// 공통 Status 라벨/순서/색상 정의
export const STATUS_SEQUENCE = ["ESOP_STARTED", "MAIN_COMPLETE", "PARTIAL_COMPLETE", "COMPLETE"]

export const STATUS_LABELS = {
  ESOP_STARTED: "ESOP시작",
  MAIN_COMPLETE: "MAIN완료",
  PARTIAL_COMPLETE: "계측중",
  COMPLETE: "완료",
}

export const STATUS_COLORS = {
  ESOP_STARTED: "color-mix(in oklab, var(--primary) 20%, white)",
  MAIN_COMPLETE: "color-mix(in oklab, var(--primary) 35%, white)",
  PARTIAL_COMPLETE: "color-mix(in oklab, var(--primary) 80%, white)",
  COMPLETE: "var(--muted-foreground)",
}
