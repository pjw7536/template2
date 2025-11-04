// src/features/line-dashboard/components/data-table/cells/NeedToSendCell.jsx
"use client"

import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { Check, CalendarCheck2, CalendarX2, XCircle } from "lucide-react"

import { makeCellKey } from "../utils/cellState"
import { buildToastOptions } from "../utils/toast"

/* ============================================================================
 * NeedToSendCell
 * - needtosend(0/1) 값을 토글하는 원형 버튼 셀
 * - 저장 성공/취소/실패에 따라 토스트 메시지 표시
 * - 비활성(disabled)이면 클릭/키보드 토글 차단
 * - 접근성(a11y): role="switch", aria-checked, 키보드(Enter/Space) 지원
 * ========================================================================== */

/* =========================
 * 1) 공통 상수/유틸
 * ======================= */

/** 정수 0/1로 안전 변환 (그 외 값은 0으로 취급) */
function to01(v) {
  const n = Number(v)
  return Number.isFinite(n) && n === 1 ? 1 : 0
}

/** 토스트 도우미: 성공/정보/실패 각각 간단한 헬퍼로 래핑 */
function showReserveToast() {
  toast.success("예약 성공", {
    description: "E-SOP Inform 예약 되었습니다.",
    icon: <CalendarCheck2 className="h-5 w-5 text-blue-500" />,
    ...buildToastOptions({ color: "#065f46", duration: 1800 }),
  })
}

function showCancelToast() {
  toast("예약 취소", {
    description: "E-SOP Inform 예약 취소 되었습니다.",
    icon: <CalendarX2 className="h-5 w-5 text-sky-600" />,
    ...buildToastOptions({ color: "#1e40af", duration: 1800 }),
  })
}

function showErrorToast(msg) {
  toast.error("저장 실패", {
    description: msg || "저장 중 오류가 발생했습니다.",
    icon: <XCircle className="h-5 w-5 text-red-500" />,
    ...buildToastOptions({ color: "#991b1b", duration: 3000 }),
  })
}

/* =========================
 * 2) 컴포넌트
 * ======================= */
export function NeedToSendCell({
  meta,
  recordId,
  baseValue,
  disabled = false,
  disabledReason = "이미 JIRA 전송됨 (needtosend 수정 불가)",
}) {
  // 메타에서 임시 드래프트 값(사용자가 토글했으나 서버 저장 전) 우선 사용
  const draftValue = meta?.needToSendDrafts?.[recordId]
  const nextValue = draftValue ?? baseValue
  const isChecked = to01(nextValue) === 1

  // 저장 중 상태: 같은 셀에 대한 동시 요청 방지
  const savingKey = makeCellKey(recordId, "needtosend")
  const isSaving = Boolean(meta?.updatingCells?.[savingKey])

  // ────────────────────────────────────────────────
  // 토글 로직 (클릭/키보드 모두 이 로직 호출)
  // ────────────────────────────────────────────────
  const toggle = async () => {
    // ⛔ 비활성 또는 저장 중이면 즉시 중단
    if (disabled) {
      toast.info(disabledReason)
      return
    }
    if (isSaving) return

    const targetValue = isChecked ? 0 : 1

    // 드래프트/에러 초기화
    meta?.setNeedToSendDraftValue?.(recordId, targetValue)
    meta?.clearUpdateError?.(savingKey)

    try {
      // 서버에 실제 업데이트 요청 (성공 시 true 가정)
      const ok = await meta?.handleUpdate?.(recordId, { needtosend: targetValue })

      // 성공
      if (ok) {
        meta?.removeNeedToSendDraftValue?.(recordId)
        targetValue === 1 ? showReserveToast() : showCancelToast()
        return
      }

      // 실패(명시적 false)
      const msg = meta?.updateErrors?.[savingKey]
      showErrorToast(msg)
    } catch (err) {
      // 예외 발생 시에도 동일하게 실패 처리
      showErrorToast(err?.message)
    } finally {
      // 실패했든 성공했든 드래프트는 정리(성공 시 위에서 이미 제거했지만 중복 제거 OK)
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
      {/* ✅ 원형 토글 버튼 (role='switch' + aria-checked로 스크린리더 친화적) */}
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
