// src/features/line-dashboard/utils/commentUtils.js
// Comment 문자열에서 보이는 부분과 숨김 마커를 안전하게 다루기 위한 유틸입니다.

export const COMMENT_MARK = "$@$"

/** comment 문자열을 보이는 텍스트와 마커 포함 suffix로 분리합니다. */
export function splitComment(raw) {
  const value = typeof raw === "string" ? raw : ""
  const idx = value.indexOf(COMMENT_MARK)
  if (idx === -1) return { visibleText: value, suffixWithMarker: "" }
  return {
    visibleText: value.slice(0, idx),
    suffixWithMarker: value.slice(idx),
  }
}

/** 분리된 comment 파트를 다시 합칩니다. */
export function composeComment(visibleText, suffixWithMarker) {
  const safeVisible = visibleText ?? ""
  const safeSuffix = suffixWithMarker ?? ""
  return `${safeVisible}${safeSuffix}`
}
