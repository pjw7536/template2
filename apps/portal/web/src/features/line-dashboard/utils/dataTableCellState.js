// src/features/line-dashboard/utils/dataTableCellState.js
// 셀 상태 관리를 위한 공통 유틸입니다.

/**
 * 행 ID와 필드명을 합쳐 일관된 셀 키를 만듭니다.
 * - CommentCell / NeedToSendCell 등에서 동일한 규칙으로 사용합니다.
 * - recordId나 field가 비어 있어도 안전하게 문자열로 변환합니다.
 */
export function makeCellKey(recordId, field) {
  const safeId = String(recordId ?? "")
  const safeField = String(field ?? "")
  return `${safeId}:${safeField}`
}
