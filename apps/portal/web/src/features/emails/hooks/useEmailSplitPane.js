import { useEffect, useRef, useState } from "react"

import {
  clampEmailListWidth,
  EMAIL_SPLIT_GAP_PX,
} from "../utils/inboxController"

const DEFAULT_LIST_RATIO = 0.45

export function useEmailSplitPane() {
  const [listWidth, setListWidth] = useState(420)
  const [isDragging, setIsDragging] = useState(false)
  const splitPaneRef = useRef(null)
  const dragCleanupRef = useRef(null)

  const stopDragging = () => {
    if (!dragCleanupRef.current) return
    dragCleanupRef.current()
    dragCleanupRef.current = null
  }

  const handleResizeStart = (event) => {
    if (!splitPaneRef.current) return
    event.preventDefault()
    stopDragging()
    setIsDragging(true)

    const handlePointerMove = (moveEvent) => {
      const container = splitPaneRef.current
      if (!container) return
      const { left } = container.getBoundingClientRect()
      const proposedWidth = moveEvent.clientX - left
      setListWidth(clampEmailListWidth(proposedWidth, container))
    }

    const handlePointerEnd = () => {
      setIsDragging(false)
      stopDragging()
    }

    dragCleanupRef.current = () => {
      window.removeEventListener("pointermove", handlePointerMove)
      window.removeEventListener("pointerup", handlePointerEnd)
      window.removeEventListener("pointercancel", handlePointerEnd)
    }

    window.addEventListener("pointermove", handlePointerMove)
    window.addEventListener("pointerup", handlePointerEnd)
    window.addEventListener("pointercancel", handlePointerEnd)
  }

  useEffect(() => {
    const container = splitPaneRef.current
    if (!container) return
    const { width } = container.getBoundingClientRect()
    if (!width) return

    setListWidth(clampEmailListWidth(width * DEFAULT_LIST_RATIO, container))
  }, [])

  useEffect(() => {
    const handleResize = () => {
      const container = splitPaneRef.current
      if (!container) return
      setListWidth((current) => clampEmailListWidth(current, container))
    }
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  useEffect(
    () => () => {
      if (!dragCleanupRef.current) return
      dragCleanupRef.current()
      dragCleanupRef.current = null
    },
    [],
  )

  return {
    splitPaneRef,
    splitPaneStyles: {
      "--email-list-width": `${listWidth}px`,
      "--email-handle-offset": `${listWidth + EMAIL_SPLIT_GAP_PX / 2}px`,
    },
    isDragging,
    handleResizeStart,
  }
}
