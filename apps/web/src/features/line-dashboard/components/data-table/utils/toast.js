// src/features/line-dashboard/components/data-table/utils/toast.js
// 토스트 옵션을 일관되게 만들기 위한 도우미입니다.

/* ============================================================================
 * ✅ 공통 스타일: CommentCell / NeedToSendCell 등에서 재사용
 * ----------------------------------------------------------------------------
 * - 동일한 여백/타이포를 유지하면 UI 인상이 통일됩니다.
 * - color(글자색)만 상황별로 바꿔 끼울 수 있도록 합니다.
 * ========================================================================== */
export const TOAST_BASE_STYLE = {
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  gap: "20px",
  fontWeight: 600,
  fontSize: "14px",
  padding: "15px 20px",
  borderRadius: "8px",
  backgroundColor: "var(--popover)",
  color: "var(--popover-foreground)",
  border: "1px solid var(--border)",
}

/**
 * 공통 스타일에 색상/지속시간만 입혀서 반환합니다.
 * - color: 글자색(상황별 강조)
 * - duration: 토스트 유지 시간(ms)
 */
export function buildToastOptions({ color, duration = 2000 } = {}) {
  return {
    duration,
    style: {
      ...TOAST_BASE_STYLE,
      ...(color ? { color } : {}),
    },
  }
}
