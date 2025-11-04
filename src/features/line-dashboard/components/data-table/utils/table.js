// src/features/line-dashboard/components/data-table/utils/table.js
// 셀/헤더 정렬을 Tailwind 클래스와 연결해 주는 유틸입니다.
const TEXT_ALIGN_CLASS = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
}

const JUSTIFY_ALIGN_CLASS = {
  left: "justify-start",
  center: "justify-center",
  right: "justify-end",
}

// meta에 지정된 정렬 정보를 기반으로 헤더 정렬을 구합니다.
export function resolveHeaderAlignment(meta) {
  return meta?.alignment?.header ?? meta?.alignment?.cell ?? "left"
}

// 셀 정렬은 헤더 값을 예비값으로 사용해 보정합니다.
export function resolveCellAlignment(meta) {
  return meta?.alignment?.cell ?? meta?.alignment?.header ?? "left"
}

export function getTextAlignClass(alignment = "left") {
  return TEXT_ALIGN_CLASS[alignment] ?? TEXT_ALIGN_CLASS.left
}

export function getJustifyClass(alignment = "left") {
  return JUSTIFY_ALIGN_CLASS[alignment] ?? JUSTIFY_ALIGN_CLASS.left
}

// 문자열 "null" 같은 경우까지 빈 값으로 간주해 깔끔하게 표시합니다.
export function isNullishDisplay(value) {
  if (value == null) return true
  if (typeof value === "string" && value.trim().toLowerCase() === "null") return true
  return false
}
