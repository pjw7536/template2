// src/features/line-dashboard/components/data-table/cells/NeedToSendCell.jsx
"use client"

import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { Check, CalendarCheck2, CalendarX2, XCircle } from "lucide-react"

import { makeCellKey } from "../utils/cellState"
import { buildToastOptions } from "../utils/toast"

/* ============================================================================
 * NeedToSendCell (Boolean 버전)
 * - needtosend 값을 boolean 으로 토글/표시
 * - 서버로는 { needtosend: true|false } 전송
 * - 과거 0/1, "Y"/"N" 등도 안전 변환
 * ========================================================================== */

/* =========================
 * 1) 유틸
 * ======================= */

/** 다양한 값(0/1, "0"/"1", "Y"/"N", "true"/"false", bool)을 안전하게 boolean 으로 변환 */
function toBool(v) {
  if (typeof v === "boolean") return v
  if (v == null) return false

  // 숫자형
  if (typeof v === "number") return v === 1

  // 문자열형
  const s = String(v).trim().toLowerCase()
  if (s === "1" || s === "y" || s === "yes" || s === "true") return true
  if (s === "0" || s === "n" || s === "no" || s === "false") return false

  // 그 외는 falsy 취급
  return false
}

/** 토스트 도우미 */
function showReserveToast() {
  toast.success("예약 성공", {
    description: "E-SOP Inform 예약 되었습니다.",
    icon: <CalendarCheck2 className="h-5 w-5" />,
    ...buildToastOptions({ color: "#065f46", duration: 1800 }),
  })
}
function showCancelToast() {
  toast("예약 취소", {
    description: "E-SOP Inform 예약 취소 되었습니다.",
    icon: <CalendarX2 className="h-5 w-5" />,
    ...buildToastOptions({ color: "#1e40af", duration: 1800 }),
  })
}
function showErrorToast(msg) {
  toast.error("저장 실패", {
    description: msg || "저장 중 오류가 발생했습니다.",
    icon: <XCircle className="h-5 w-5" />,
    ...buildToastOptions({ color: "#991b1b", duration: 3000 }),
  })
}

/* =========================
 * 2) 컴포넌트
 * ======================= */
export function NeedToSendCell({
  meta,
  recordId,
  baseValue, // 서버/테이블 원본값 (true/false 또는 과거 0/1 등)
  disabled = false,
  disabledReason = "이미 JIRA 전송됨 (needtosend 수정 불가)",
}) {
  // 메타에서 임시 드래프트 값(서버 저장 전)을 우선 사용
  const draftValue = meta?.needToSendDrafts?.[recordId]
  const nextValue = draftValue ?? baseValue

  // 항상 boolean 으로 표현
  const isChecked = toBool(nextValue)

  // 저장 중 상태: 같은 셀 동시 요청 방지
  const savingKey = makeCellKey(recordId, "needtosend")
  const isSaving = Boolean(meta?.updatingCells?.[savingKey])

  // ────────────────────────────────────────────────
  // 토글 로직 (클릭/키보드)
  // ────────────────────────────────────────────────
  const toggle = async () => {
    if (disabled) {
      toast.info(disabledReason)
      return
    }
    if (isSaving) return

    // boolean 토글
    const targetValue = !isChecked

    // 드래프트/에러 초기화
    meta?.setNeedToSendDraftValue?.(recordId, targetValue)
    meta?.clearUpdateError?.(savingKey)

    try {
      // 서버에 실제 업데이트 요청 — boolean으로 전송
      const ok = await meta?.handleUpdate?.(recordId, { needtosend: targetValue })

      if (ok) {
        meta?.removeNeedToSendDraftValue?.(recordId)
        targetValue ? showReserveToast() : showCancelToast()
        return
      }

      const msg = meta?.updateErrors?.[savingKey]
      showErrorToast(msg)
    } catch (err) {
      showErrorToast(err?.message)
    } finally {
      // 성공/실패와 무관하게 드래프트는 정리(성공 시 이미 제거됨)
      meta?.removeNeedToSendDraftValue?.(recordId)
    }
  }

  // ────────────────────────────────────────────────
  // 키보드 접근성: Space/Enter 로 토글
  // ────────────────────────────────────────────────
  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      toggle()
    }
  }

  const titleText = disabled ? disabledReason : isChecked ? "Need to send" : "Not selected"

  return (
    <div className="inline-flex justify-center">
      {/* ✅ 원형 토글 버튼 (role='switch' + aria-checked=true|false) */}
      <button
        type="button"
        onClick={toggle}
        onKeyDown={onKeyDown}
        disabled={disabled || isSaving}
        role="switch"
        aria-checked={isChecked}
        aria-disabled={disabled || isSaving}
        aria-label={titleText}
        title={titleText}
        className={cn(
          "inline-flex h-5 w-5 items-center justify-center rounded-full border transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2",
          isChecked
            ? "bg-blue-500 border-blue-500"
            : "border-muted-foreground/30 hover:border-blue-300",
          (disabled || isSaving) && "bg-gray-400 border-gray-400 cursor-not-allowed"
        )}
      >
        {isChecked && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
      </button>
    </div>
  )
}

export default NeedToSendCell
