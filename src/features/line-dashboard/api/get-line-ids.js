// src/features/line-dashboard/api/get-line-ids.js
import { runQuery } from "@/lib/db"

// 한 곳에서만 사용하는 테이블 이름을 상수로 정의해 두면 오타를 줄일 수 있습니다.
const LINE_SDWT_TABLE_NAME = "line_sdwt"
const QUERY_FIND_DISTINCT_LINE_IDS = `
  SELECT DISTINCT line_id
  FROM ${LINE_SDWT_TABLE_NAME}
  WHERE line_id IS NOT NULL AND line_id <> ''
  ORDER BY line_id
`

/**
 * 라인 선택 드롭다운 등에 사용할 고유 line_id 목록을 가져옵니다.
 * - SQL에서 NULL/빈 문자열을 제거한 뒤
 * - 문자열이 아닌 값이 섞였을 가능성까지 체크해 필터링합니다.
 */
export async function getDistinctLineIds() {
  const rows = await runQuery(QUERY_FIND_DISTINCT_LINE_IDS)

  return rows
    .map((row) => row?.line_id)
    .filter((lineId) => typeof lineId === "string" && lineId.trim().length > 0)
    .map((lineId) => lineId.trim())
}
