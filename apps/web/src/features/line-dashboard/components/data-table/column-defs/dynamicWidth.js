// src/features/line-dashboard/components/data-table/column-defs/dynamicWidth.js
import { DEFAULT_MAX_WIDTH, DEFAULT_MIN_WIDTH, DEFAULT_TEXT_WIDTH } from "./constants"

// 사용자 설정 값을 기반으로 size/min/max를 계산합니다.
export function resolveColumnSizes(colKey, config) {
  const configuredWidth = Number(config.width?.[colKey])
  const size =
    Number.isFinite(configuredWidth) && configuredWidth > 0
      ? configuredWidth
      : DEFAULT_TEXT_WIDTH

  const minSize = Math.min(Math.max(DEFAULT_MIN_WIDTH, Math.floor(size * 0.5)), size)
  const maxSize = Math.max(DEFAULT_MAX_WIDTH, Math.ceil(size * 2))
  return { size, minSize, maxSize }
}
