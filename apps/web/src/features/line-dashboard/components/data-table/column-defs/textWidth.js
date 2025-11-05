// src/features/line-dashboard/components/data-table/column-defs/textWidth.js
import { DEFAULT_MIN_WIDTH } from "./constants"

// 각 행의 첫 줄 길이를 기준으로 텍스트 컬럼의 자연 폭을 추정합니다.
// 한글처럼 넓은 문자는 2칸으로 계산해 가독성을 확보합니다.
export function computeAutoTextWidthFromRows(
  rows,
  key,
  { charUnitPx = 7, cellPadding = 40, min = DEFAULT_MIN_WIDTH, max = 720 } = {}
) {
  if (!Array.isArray(rows) || rows.length === 0) return null
  let maxUnits = 0

  for (const row of rows) {
    const value = row?.[key]
    const str = value == null ? "" : String(value)
    const line = str.replace(/\t/g, "    ").split(/\r?\n/)[0] ?? ""
    let units = 0

    for (const ch of Array.from(line)) {
      const codePoint = ch.codePointAt(0) ?? 0
      if (codePoint === 0) continue
      if (codePoint <= 0x1f || (codePoint >= 0x7f && codePoint <= 0x9f)) continue
      units += codePoint <= 0xff ? 1 : 2
    }

    if (units > maxUnits) maxUnits = units
  }

  if (maxUnits === 0) return null
  const width = Math.ceil(maxUnits * charUnitPx + cellPadding)
  return Math.max(min, Math.min(width, max))
}
