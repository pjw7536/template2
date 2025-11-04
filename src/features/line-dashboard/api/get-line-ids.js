// src/features/line-dashboard/api/get-line-ids.js
import { runQuery } from "@/lib/db"

/* ============================================================================
 * ✅ 상수 정의
 * - 테이블 이름을 상수로 지정하면 오타나 문자열 실수를 방지할 수 있습니다.
 * - 쿼리를 문자열로 작성할 때 `${}`로 상수를 안전하게 삽입합니다.
 * ========================================================================== */
const LINE_SDWT_TABLE_NAME = "line_sdwt"

// 고유 line_id 목록을 가져오는 SQL 쿼리
const QUERY_FIND_DISTINCT_LINE_IDS = `
  SELECT DISTINCT line_id
  FROM ${LINE_SDWT_TABLE_NAME}
  WHERE line_id IS NOT NULL AND line_id <> ''
  ORDER BY line_id
`

/* ============================================================================
 * ✅ getDistinctLineIds()
 * - line_sdwt 테이블에서 중복 없는(line_id) 목록을 가져오는 함수입니다.
 * - NULL 값이나 빈 문자열('')은 제외합니다.
 * - 문자열이 아닌 타입(숫자, null 등)이 섞여 있을 가능성도 대비합니다.
 * ========================================================================== */
export async function getDistinctLineIds() {
  // SQL 실행 결과: [{ line_id: 'LINE_A' }, { line_id: 'LINE_B' }, ...]
  const rows = await runQuery(QUERY_FIND_DISTINCT_LINE_IDS)

  // line_id 컬럼만 추출하고, 유효한 문자열만 정제해서 반환
  return rows
    .map((row) => row?.line_id) // 각 row 객체에서 line_id만 꺼냄
    .filter(
      (lineId) => typeof lineId === "string" && lineId.trim().length > 0
    ) // 문자열만 필터링 + 공백 제거
    .map((lineId) => lineId.trim()) // 좌우 공백 제거
}
