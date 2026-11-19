export const METRICS = [
  { key: "equipment", label: "담당 가동 설비 수", unit: "대" },
  { key: "spc", label: "SPC Interlock", unit: "건" },
  { key: "fdc", label: "FDC Interlock", unit: "건" },
  { key: "apc", label: "APC 가변", unit: "건" },
  { key: "pm", label: "설비 PM", unit: "건" },
  { key: "lotHold", label: "Lot Hold", unit: "건" },
]

export const DEFAULT_WEIGHTS = { equipment: 2, spc: 1, fdc: 1, apc: 1, pm: 3, lotHold: 2 }

export function workloadTotal(record, weights) {
  return METRICS.reduce((total, { key }) => total + record[key] * weights[key], 0)
}

export function scorePerPerson(total, headcount) {
  return headcount > 0 ? total / headcount : null
}
