import { useEffect, useRef, useState } from "react"

import {
  DEFAULT_CHAT_HEIGHT,
  DEFAULT_CHAT_WIDTH,
  DEFAULT_FLOATING_BUTTON_SIZE,
  clampPosition,
  clampSize,
} from "../utils/chatWidgetBounds"

const DEFAULT_SIDEBAR_WIDTH = 208
const MIN_SIDEBAR_WIDTH = 176
const MAX_SIDEBAR_WIDTH = 360
const MIN_CHAT_CONTENT_WIDTH = 280
const SIDEBAR_KEYBOARD_STEP = 16

function getSidebarMaxWidth(widgetWidth) {
  return Math.max(
    MIN_SIDEBAR_WIDTH,
    Math.min(MAX_SIDEBAR_WIDTH, widgetWidth - MIN_CHAT_CONTENT_WIDTH),
  )
}

function clampSidebarWidth(width, widgetWidth) {
  return Math.min(
    Math.max(width, MIN_SIDEBAR_WIDTH),
    getSidebarMaxWidth(widgetWidth),
  )
}

export function useFloatingChatWindow() {
  const [isOpen, setIsOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)
  const [buttonPosition, setButtonPosition] = useState({ x: null, y: null })
  const [isDragging, setIsDragging] = useState(false)
  const [widgetPosition, setWidgetPosition] = useState({ x: null, y: null })
  const [isWidgetDragging, setIsWidgetDragging] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const [size, setSize] = useState(() => clampSize(DEFAULT_CHAT_WIDTH, DEFAULT_CHAT_HEIGHT))
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH)
  const [isSidebarResizing, setIsSidebarResizing] = useState(false)
  const sizeRef = useRef(size)
  const floatingButtonRef = useRef(null)
  const floatingButtonSizeRef = useRef({
    width: DEFAULT_FLOATING_BUTTON_SIZE,
    height: DEFAULT_FLOATING_BUTTON_SIZE,
  })
  const dragOffsetRef = useRef({ x: 0, y: 0 })
  const hasDraggedRef = useRef(false)
  const dragStartRef = useRef({ x: 0, y: 0 })
  const widgetDragOffsetRef = useRef({ x: 0, y: 0 })
  const lastWidgetPositionRef = useRef(null)
  const resizeStartRef = useRef({
    width: 0,
    height: 0,
    left: 0,
    top: 0,
    right: 0,
    bottom: 0,
    x: 0,
    y: 0,
  })
  const sidebarResizeStartRef = useRef({ width: DEFAULT_SIDEBAR_WIDTH, x: 0 })
  const resizeDirectionRef = useRef("se")
  const chatContainerRef = useRef(null)

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return
    if (widgetPosition.x !== null && widgetPosition.y !== null) return

    const offset = 16
    setWidgetPosition(
      clampPosition(
        window.innerWidth - size.width - offset,
        window.innerHeight - size.height - offset,
        size.width,
        size.height,
      ),
    )
  }, [isOpen, size.height, size.width, widgetPosition.x, widgetPosition.y])

  useEffect(() => {
    if (!isOpen || typeof document === "undefined") return

    const handlePointerDown = (event) => {
      const target = event.target
      const targetElement = target instanceof Element ? target : target?.parentElement
      const eventPath = typeof event.composedPath === "function" ? event.composedPath() : []
      const clickedInsideWidget =
        chatContainerRef.current &&
        (chatContainerRef.current.contains(targetElement) || eventPath.includes(chatContainerRef.current))
      if (clickedInsideWidget) return

      const hasPortalTarget =
        eventPath.some(
          (node) => node instanceof Element && node.hasAttribute?.("data-chat-widget-portal"),
        ) || targetElement?.closest?.("[data-chat-widget-portal]")
      if (hasPortalTarget) return

      const hasOpenWidgetPortal = document.querySelector(
        '[data-chat-widget-portal][data-state="open"]',
      )
      if (hasOpenWidgetPortal) return

      if (!chatContainerRef.current) return
      const rect = chatContainerRef.current?.getBoundingClientRect()
      if (rect) {
        const { width: buttonWidth, height: buttonHeight } = floatingButtonSizeRef.current
        setButtonPosition(
          clampPosition(
            rect.right - buttonWidth,
            rect.bottom - buttonHeight,
            buttonWidth,
            buttonHeight,
          ),
        )
      }
      setIsWidgetDragging(false)
      setIsResizing(false)
      setIsOpen(false)
    }

    document.addEventListener("pointerdown", handlePointerDown, true)
    return () => document.removeEventListener("pointerdown", handlePointerDown, true)
  }, [isOpen])

  useEffect(() => {
    if (!isOpen || typeof document === "undefined") return

    const handleKeyDown = (event) => {
      if (event.key !== "Escape") return
      const hasOpenWidgetPortal = document.querySelector(
        '[data-chat-widget-portal][data-state="open"]',
      )
      if (hasOpenWidgetPortal) return
      event.preventDefault()
      setIsWidgetDragging(false)
      setIsResizing(false)
      setIsOpen(false)
      window.requestAnimationFrame?.(() => floatingButtonRef.current?.focus())
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return

    const ensureWidgetWithinBounds = () => {
      if (isMaximized) {
        if (typeof window === "undefined") return
        const nextSize = { width: window.innerWidth, height: window.innerHeight }
        sizeRef.current = nextSize
        setSize(nextSize)
        setWidgetPosition({ x: 0, y: 0 })
        return
      }

      setSize((previousSize) => {
        const nextSize = clampSize(previousSize.width, previousSize.height)
        sizeRef.current = nextSize
        setWidgetPosition((previousPosition) => {
          if (previousPosition.x === null || previousPosition.y === null) {
            return previousPosition
          }
          const nextPosition = clampPosition(
            previousPosition.x,
            previousPosition.y,
            nextSize.width,
            nextSize.height,
          )
          if (
            nextPosition.x === previousPosition.x &&
            nextPosition.y === previousPosition.y
          ) {
            return previousPosition
          }
          return nextPosition
        })
        return nextSize
      })
    }

    ensureWidgetWithinBounds()
    if (typeof window === "undefined") return

    window.addEventListener("resize", ensureWidgetWithinBounds)
    return () => window.removeEventListener("resize", ensureWidgetWithinBounds)
  }, [isMaximized, isOpen])

  useEffect(() => {
    if (!isResizing || typeof document === "undefined") return

    const handlePointerMove = (event) => {
      const direction = resizeDirectionRef.current || "se"
      const deltaX = event.clientX - resizeStartRef.current.x
      const deltaY = event.clientY - resizeStartRef.current.y
      const isResizingWest = direction.includes("w")
      const isResizingNorth = direction.includes("n")
      const isResizingEast = direction.includes("e")
      const isResizingSouth = direction.includes("s")

      let nextWidth = resizeStartRef.current.width
      let nextHeight = resizeStartRef.current.height
      if (isResizingEast) nextWidth += deltaX
      if (isResizingWest) nextWidth -= deltaX
      if (isResizingSouth) nextHeight += deltaY
      if (isResizingNorth) nextHeight -= deltaY

      const nextSize = clampSize(nextWidth, nextHeight)
      const previousSize = sizeRef.current
      if (
        nextSize.width === previousSize.width &&
        nextSize.height === previousSize.height
      ) {
        return
      }
      const nextPosition = clampPosition(
        isResizingWest
          ? resizeStartRef.current.right - nextSize.width
          : resizeStartRef.current.left,
        isResizingNorth
          ? resizeStartRef.current.bottom - nextSize.height
          : resizeStartRef.current.top,
        nextSize.width,
        nextSize.height,
      )

      sizeRef.current = nextSize
      setSize(nextSize)
      setWidgetPosition(nextPosition)
    }

    const handlePointerUp = () => {
      resizeDirectionRef.current = "se"
      setIsResizing(false)
    }

    document.addEventListener("pointermove", handlePointerMove)
    document.addEventListener("pointerup", handlePointerUp)
    document.addEventListener("pointercancel", handlePointerUp)
    return () => {
      document.removeEventListener("pointermove", handlePointerMove)
      document.removeEventListener("pointerup", handlePointerUp)
      document.removeEventListener("pointercancel", handlePointerUp)
    }
  }, [isResizing])

  useEffect(() => {
    setSidebarWidth((previousWidth) => clampSidebarWidth(previousWidth, size.width))
  }, [size.width])

  useEffect(() => {
    if (!isSidebarResizing || typeof document === "undefined") return

    const previousCursor = document.body.style.cursor
    const previousUserSelect = document.body.style.userSelect
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"

    const handlePointerMove = (event) => {
      const deltaX = event.clientX - sidebarResizeStartRef.current.x
      setSidebarWidth(
        clampSidebarWidth(
          sidebarResizeStartRef.current.width + deltaX,
          sizeRef.current.width,
        ),
      )
    }

    const handlePointerUp = () => setIsSidebarResizing(false)

    document.addEventListener("pointermove", handlePointerMove)
    document.addEventListener("pointerup", handlePointerUp)
    document.addEventListener("pointercancel", handlePointerUp)
    return () => {
      document.body.style.cursor = previousCursor
      document.body.style.userSelect = previousUserSelect
      document.removeEventListener("pointermove", handlePointerMove)
      document.removeEventListener("pointerup", handlePointerUp)
      document.removeEventListener("pointercancel", handlePointerUp)
    }
  }, [isSidebarResizing])

  useEffect(() => {
    if (!isWidgetDragging || typeof document === "undefined") return

    const handlePointerMove = (event) => {
      const rect = chatContainerRef.current?.getBoundingClientRect()
      if (!rect) return
      setWidgetPosition(
        clampPosition(
          event.clientX - widgetDragOffsetRef.current.x,
          event.clientY - widgetDragOffsetRef.current.y,
          rect.width,
          rect.height,
        ),
      )
    }

    const handlePointerUp = () => setIsWidgetDragging(false)

    document.addEventListener("pointermove", handlePointerMove)
    document.addEventListener("pointerup", handlePointerUp)
    document.addEventListener("pointercancel", handlePointerUp)
    return () => {
      document.removeEventListener("pointermove", handlePointerMove)
      document.removeEventListener("pointerup", handlePointerUp)
      document.removeEventListener("pointercancel", handlePointerUp)
    }
  }, [isWidgetDragging])

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      buttonPosition.x !== null ||
      buttonPosition.y !== null ||
      !floatingButtonRef.current
    ) {
      return
    }

    const rect = floatingButtonRef.current.getBoundingClientRect()
    floatingButtonSizeRef.current = { width: rect.width, height: rect.height }
    const offset = 16
    setButtonPosition({
      x: window.innerWidth - rect.width - offset - 32,
      y: window.innerHeight - rect.height - offset - 5,
    })
  }, [buttonPosition.x, buttonPosition.y])

  const closeWidget = () => {
    if (typeof window !== "undefined") {
      const rect = chatContainerRef.current?.getBoundingClientRect()
      if (rect) {
        const { width: buttonWidth, height: buttonHeight } = floatingButtonSizeRef.current
        setButtonPosition(
          clampPosition(
            rect.right - buttonWidth,
            rect.bottom - buttonHeight,
            buttonWidth,
            buttonHeight,
          ),
        )
      }
    }
    setIsWidgetDragging(false)
    setIsResizing(false)
    setIsSidebarResizing(false)
    setIsOpen(false)
    window.requestAnimationFrame?.(() => floatingButtonRef.current?.focus())
  }

  const resizeWidget = (nextSize) => {
    sizeRef.current = nextSize
    setSize(nextSize)
    setWidgetPosition((previousPosition) => {
      if (typeof window === "undefined") return previousPosition
      const offset = 16
      if (previousPosition.x === null || previousPosition.y === null) {
        return clampPosition(
          window.innerWidth - nextSize.width - offset,
          window.innerHeight - nextSize.height - offset,
          nextSize.width,
          nextSize.height,
        )
      }
      return clampPosition(
        previousPosition.x,
        previousPosition.y,
        nextSize.width,
        nextSize.height,
      )
    })
  }

  const handleOpenFullChat = () => {
    if (isMaximized) return
    if (widgetPosition.x !== null && widgetPosition.y !== null) {
      lastWidgetPositionRef.current = { x: widgetPosition.x, y: widgetPosition.y }
    }
    setIsMaximized(true)
    if (typeof window === "undefined") return
    const nextSize = { width: window.innerWidth, height: window.innerHeight }
    sizeRef.current = nextSize
    setSize(nextSize)
    setWidgetPosition({ x: 0, y: 0 })
  }

  const handleRestoreDefaultSize = () => {
    const nextSize = clampSize(DEFAULT_CHAT_WIDTH, DEFAULT_CHAT_HEIGHT)
    setIsMaximized(false)
    resizeWidget(nextSize)
    if (lastWidgetPositionRef.current) {
      setWidgetPosition(
        clampPosition(
          lastWidgetPositionRef.current.x,
          lastWidgetPositionRef.current.y,
          nextSize.width,
          nextSize.height,
        ),
      )
    }
  }

  const handleFloatingButtonPointerDown = (event) => {
    const rect = floatingButtonRef.current?.getBoundingClientRect()
    if (!rect) return
    dragOffsetRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
    dragStartRef.current = { x: event.clientX, y: event.clientY }
    hasDraggedRef.current = false
    setIsDragging(true)
    floatingButtonRef.current.setPointerCapture?.(event.pointerId)
  }

  const handleFloatingButtonPointerMove = (event) => {
    if (!isDragging || !floatingButtonRef.current) return
    const rect = floatingButtonRef.current.getBoundingClientRect()
    const nextPosition = clampPosition(
      event.clientX - dragOffsetRef.current.x,
      event.clientY - dragOffsetRef.current.y,
      rect.width,
      rect.height,
    )
    if (
      !hasDraggedRef.current &&
      (Math.abs(event.clientX - dragStartRef.current.x) > 2 ||
        Math.abs(event.clientY - dragStartRef.current.y) > 2)
    ) {
      hasDraggedRef.current = true
    }
    setButtonPosition(nextPosition)
  }

  const handleFloatingButtonPointerUp = (event) => {
    if (!isDragging) return
    setIsDragging(false)
    floatingButtonRef.current?.releasePointerCapture(event.pointerId)
  }

  const handleFloatingButtonClick = () => {
    if (hasDraggedRef.current) {
      hasDraggedRef.current = false
      return
    }

    const rect = floatingButtonRef.current?.getBoundingClientRect()
    if (rect) {
      setWidgetPosition(
        clampPosition(
          rect.right - size.width,
          rect.bottom - size.height,
          size.width,
          size.height,
        ),
      )
    } else if (typeof window !== "undefined") {
      const offset = 16
      setWidgetPosition(
        clampPosition(
          window.innerWidth - size.width - offset,
          window.innerHeight - size.height - offset,
          size.width,
          size.height,
        ),
      )
    }
    setIsOpen(true)
  }

  const handleWidgetHeaderPointerDown = (event) => {
    if (!chatContainerRef.current || isResizing || isMaximized) return
    const target = event.target
    const targetElement = target instanceof Element ? target : target?.parentElement
    const isInteractiveElement = targetElement?.closest?.(
      'button, a, input, textarea, select, [data-chat-widget-no-drag="true"]',
    )
    if (isInteractiveElement) return

    event.preventDefault()
    const rect = chatContainerRef.current.getBoundingClientRect()
    widgetDragOffsetRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
    setIsWidgetDragging(true)
  }

  const handleResizePointerDown = (direction) => (event) => {
    event.preventDefault()
    event.stopPropagation()
    if (isMaximized) return
    const rect = chatContainerRef.current?.getBoundingClientRect()
    if (!rect) return

    resizeDirectionRef.current = direction
    resizeStartRef.current = {
      width: rect.width,
      height: rect.height,
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      x: event.clientX,
      y: event.clientY,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setIsResizing(true)
  }

  const handleSidebarResizePointerDown = (event) => {
    event.preventDefault()
    event.stopPropagation()
    sidebarResizeStartRef.current = { width: sidebarWidth, x: event.clientX }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setIsSidebarResizing(true)
  }

  const handleSidebarResizeKeyDown = (event) => {
    let nextWidth = sidebarWidth
    if (event.key === "ArrowLeft") nextWidth -= SIDEBAR_KEYBOARD_STEP
    else if (event.key === "ArrowRight") nextWidth += SIDEBAR_KEYBOARD_STEP
    else if (event.key === "Home") nextWidth = MIN_SIDEBAR_WIDTH
    else if (event.key === "End") nextWidth = getSidebarMaxWidth(size.width)
    else return

    event.preventDefault()
    setSidebarWidth(clampSidebarWidth(nextWidth, size.width))
  }

  return {
    buttonPosition,
    chatContainerRef,
    closeWidget,
    floatingButtonRef,
    handleFloatingButtonClick,
    handleFloatingButtonPointerDown,
    handleFloatingButtonPointerMove,
    handleFloatingButtonPointerUp,
    handleOpenFullChat,
    handleResizePointerDown,
    handleRestoreDefaultSize,
    handleSidebarResizeKeyDown,
    handleSidebarResizePointerDown,
    handleWidgetHeaderPointerDown,
    isMaximized,
    isOpen,
    isSidebarOpen,
    sidebarMaxWidth: getSidebarMaxWidth(size.width),
    sidebarMinWidth: MIN_SIDEBAR_WIDTH,
    sidebarWidth,
    size,
    toggleSidebar: () => setIsSidebarOpen((previous) => !previous),
    widgetPosition,
  }
}
