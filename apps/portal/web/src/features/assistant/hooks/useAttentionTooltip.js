import { useEffect, useRef, useState } from "react"

import { useAuth } from "@/lib/auth"

const TOOLTIP_TEXT = "무엇이든 물어보세요"
const TOOLTIP_TYPING_DURATION_MS = 300
const TOOLTIP_VISIBLE_DURATION_MS = 3000

function clearAttentionTooltipTimers(timeoutRef, intervalRef) {
  if (timeoutRef.current) {
    clearTimeout(timeoutRef.current)
    timeoutRef.current = null
  }

  if (intervalRef.current) {
    clearInterval(intervalRef.current)
    intervalRef.current = null
  }
}

function showAttentionTooltip(setIsVisible, setText, timeoutRef, intervalRef) {
  if (typeof window === "undefined") return

  setIsVisible(true)
  setText("")

  clearAttentionTooltipTimers(timeoutRef, intervalRef)

  const totalLength = TOOLTIP_TEXT.length

  if (totalLength > 0) {
    const intervalMs = Math.max(
      20,
      Math.floor(TOOLTIP_TYPING_DURATION_MS / totalLength),
    )
    let index = 1

    setText(TOOLTIP_TEXT.slice(0, index))

    if (totalLength > 1) {
      const intervalId = window.setInterval(() => {
        index += 1
        setText(TOOLTIP_TEXT.slice(0, index))

        if (index >= totalLength) {
          clearInterval(intervalId)
          if (intervalRef.current === intervalId) {
            intervalRef.current = null
          }
        }
      }, intervalMs)

      intervalRef.current = intervalId
    }
  }

  timeoutRef.current = window.setTimeout(() => {
    setIsVisible(false)
    setText("")
    clearAttentionTooltipTimers(timeoutRef, intervalRef)
  }, TOOLTIP_VISIBLE_DURATION_MS)
}

export function useAttentionTooltip({ isOpen, isHomePage }) {
  const { user } = useAuth()
  const hasUser = Boolean(user)
  const [shouldShowAttentionTooltip, setShouldShowAttentionTooltip] = useState(false)
  const [isAttentionTooltipVisible, setIsAttentionTooltipVisible] = useState(false)
  const [attentionTooltipText, setAttentionTooltipText] = useState("")
  const timeoutRef = useRef(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!hasUser || !isHomePage) return

    setShouldShowAttentionTooltip(true)
  }, [hasUser, isHomePage])

  useEffect(() => {
    if (!shouldShowAttentionTooltip || !hasUser || isOpen || !isHomePage) {
      return undefined
    }

    showAttentionTooltip(
      setIsAttentionTooltipVisible,
      setAttentionTooltipText,
      timeoutRef,
      intervalRef,
    )

    return () => {
      clearAttentionTooltipTimers(timeoutRef, intervalRef)
    }
  }, [hasUser, isHomePage, isOpen, shouldShowAttentionTooltip])

  useEffect(() => {
    if (hasUser && !isOpen && isHomePage) return

    setShouldShowAttentionTooltip(false)
    setIsAttentionTooltipVisible(false)
    setAttentionTooltipText("")
    clearAttentionTooltipTimers(timeoutRef, intervalRef)
  }, [hasUser, isHomePage, isOpen])

  return { isAttentionTooltipVisible, attentionTooltipText }
}
