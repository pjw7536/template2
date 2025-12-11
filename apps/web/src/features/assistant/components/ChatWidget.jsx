import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { Bot, Minus, PanelLeft, SquareArrowOutUpRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ChatComposer } from "./ChatComposer"
import { ChatErrorBanner } from "./ChatErrorBanner"
import { ChatMessages } from "./ChatMessages"
import { RoomList } from "./RoomList"
import { useChatSession } from "../hooks/useChatSession"
import { sortRoomsByRecentQuestion } from "../utils/chatRooms"

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [input, setInput] = useState("")
  const [buttonPosition, setButtonPosition] = useState({ x: null, y: null })
  const [isDragging, setIsDragging] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const {
    rooms,
    activeRoomId,
    messages,
    messagesByRoom,
    isSending,
    errorMessage,
    clearError,
    sendMessage,
    selectRoom,
    createRoom,
  } = useChatSession()
  const inputRef = useRef(null)
  const floatingButtonRef = useRef(null)
  const dragOffsetRef = useRef({ x: 0, y: 0 })
  const hasDraggedRef = useRef(false)
  const dragStartRef = useRef({ x: 0, y: 0 })
  const chatContainerRef = useRef(null)
  const initializedSessionRef = useRef(false)
  const wasSendingRef = useRef(false)
  const sortedRooms = sortRoomsByRecentQuestion(rooms, messagesByRoom)

  const isChatPage =
    typeof location?.pathname === "string" && location.pathname.startsWith("/assistant")

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen || typeof document === "undefined") return

    const handlePointerDown = (event) => {
      if (chatContainerRef.current && !chatContainerRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener("pointerdown", handlePointerDown)
    return () => document.removeEventListener("pointerdown", handlePointerDown)
  }, [isOpen])

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
    const offset = 16
    setButtonPosition({
      x: window.innerWidth - rect.width - offset,
      y: window.innerHeight - rect.height - offset,
    })
  }, [buttonPosition.x, buttonPosition.y])

  useEffect(() => {
    if (initializedSessionRef.current) return
    const hasPreviousConversation = Object.values(messagesByRoom || {}).some((roomMessages) =>
      Array.isArray(roomMessages) && roomMessages.some((message) => message?.role === "user")
    )
    const hasExistingRooms = Array.isArray(rooms) && rooms.length > 0
    if (!hasPreviousConversation && !hasExistingRooms) {
      createRoom("새 대화")
    }
    initializedSessionRef.current = true
  }, [createRoom, messagesByRoom, rooms])

  useEffect(() => {
    if (!isOpen) {
      wasSendingRef.current = isSending
      return
    }

    if (!isSending && wasSendingRef.current && inputRef.current) {
      inputRef.current.focus()
    }

    wasSendingRef.current = isSending
  }, [isSending, isOpen])

  if (isChatPage) {
    return null
  }

  const clampPosition = (x, y, width, height) => {
    if (typeof window === "undefined") return { x, y }
    return {
      x: Math.min(Math.max(x, 8), window.innerWidth - width - 8),
      y: Math.min(Math.max(y, 8), window.innerHeight - height - 8),
    }
  }

  const focusInput = () => {
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim() || isSending) return
    try {
      await sendMessage(input)
      setInput("")
    } finally {
      focusInput()
    }
  }

  const handleOpenFullChat = () => {
    navigate("/assistant", {
      state: {
        initialRooms: rooms,
        initialMessagesByRoom: messagesByRoom,
        initialActiveRoomId: activeRoomId,
      },
    })
    setIsOpen(false)
  }

  const handleFloatingButtonPointerDown = (event) => {
    if (!floatingButtonRef.current) return

    const rect = floatingButtonRef.current.getBoundingClientRect()
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
    setIsOpen(true)
  }

  if (!isOpen) {
    const isPositioned = buttonPosition.x !== null && buttonPosition.y !== null

    return (
      <div
        className={[
          "fixed z-50",
          isPositioned ? "cursor-grab active:cursor-grabbing" : "bottom-4 right-4",
        ]
          .filter(Boolean)
          .join(" ")}
        style={
          isPositioned
            ? { left: buttonPosition.x, top: buttonPosition.y }
            : undefined
        }
        onPointerDown={handleFloatingButtonPointerDown}
        onPointerMove={handleFloatingButtonPointerMove}
        onPointerUp={handleFloatingButtonPointerUp}
      >
        <Button
          size="icon"
          className="h-12 w-12 rounded-full shadow-lg"
          onClick={handleFloatingButtonClick}
          aria-label="Open assistant chat"
          ref={floatingButtonRef}
        >
          <Bot className="size-8" />
          <span className="sr-only">도움받기</span>
        </Button>
      </div>
    )
  }

  return (
    <div
      ref={chatContainerRef}
      className="fixed bottom-4 right-4 z-50 w-[calc(100%-1.5rem)] max-w-lg"
    >
      <div className="flex h-[520px] max-h-[80vh] flex-col overflow-hidden rounded-xl border bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b bg-card px-4 py-3">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setIsSidebarOpen((prev) => !prev)}
              aria-label={isSidebarOpen ? "대화방 목록 닫기" : "대화방 목록 열기"}
            >
              <PanelLeft className="h-3 w-3" />
            </Button>

            <div className="mx-3 flex items-center gap-3">
              <span className="flex h-2 w-2 rounded-full bg-primary ring-2 ring-primary/30" />
              <p className="text-sm font-semibold leading-tight">
                Etch AI Assistant
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleOpenFullChat}
              aria-label="Open full chat page"
            >
              <SquareArrowOutUpRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setIsOpen(false)}
              aria-label="Minimize chat widget"
            >
              <Minus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {isSidebarOpen && (
            <aside className="flex w-52 shrink-0 flex-col border-r bg-muted/40">
              <div className="flex items-center justify-between px-3 py-2">
                <div className="space-y-0.5">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">대화방</p>
                  <p className="text-sm font-semibold text-foreground">최근 {rooms.length}개</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={() => createRoom()}
                >
                  새 대화
                </Button>
              </div>
              <div className="mb-2 flex items-center justify-between border-b px-3 pb-2" />
              <div className="space-y-1 overflow-y-auto px-2 pb-3">
                <RoomList rooms={sortedRooms} activeRoomId={activeRoomId} onSelectRoom={selectRoom} />
              </div>
            </aside>
          )}

          <div className="flex flex-1 flex-col overflow-hidden">
            <ChatMessages messages={messages} isSending={isSending} />

            <ChatErrorBanner message={errorMessage} onDismiss={clearError} />

            <ChatComposer
              inputId="chat-widget-input"
              label="어시스턴트에게 질문하기"
              inputRef={inputRef}
              inputValue={input}
              onInputChange={(event) => setInput(event.target.value)}
              onSubmit={handleSubmit}
              isSending={isSending}
              placeholder="궁금한 점을 입력하세요. Shift+Enter로 줄바꿈"
              footerLeft={
                <button
                  type="button"
                  className="text-primary underline underline-offset-4"
                  onClick={handleOpenFullChat}
                >
                  전체 화면에서 이어서 보기
                </button>
              }
              footerRight="베타 · LLM API 연결"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
