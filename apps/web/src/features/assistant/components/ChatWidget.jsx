import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { Bot, Loader2, Minus, PanelLeft, RefreshCw, Send, SquareArrowOutUpRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { AssistantStatusIndicator } from "./AssistantStatusIndicator"
import { useChatSession } from "../hooks/useChatSession"

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
    resetConversation,
    selectRoom,
    createRoom,
  } = useChatSession()
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const floatingButtonRef = useRef(null)
  const dragOffsetRef = useRef({ x: 0, y: 0 })
  const hasDraggedRef = useRef(false)
  const dragStartRef = useRef({ x: 0, y: 0 })
  const chatContainerRef = useRef(null)
  const initializedSessionRef = useRef(false)
  const activeRoom = rooms.find((room) => room.id === activeRoomId) || rooms[0] || { name: "대화방" }
  const getMessageTimestamp = (message) => {
    if (!message?.id) return 0
    const parts = String(message.id).split("-")
    const ts = Number(parts[1])
    return Number.isFinite(ts) ? ts : 0
  }
  const getLastQuestionTimestamp = (roomId) => {
    const roomMessages = messagesByRoom[roomId] || []
    const lastUser = [...roomMessages].reverse().find((msg) => msg.role === "user")
    if (lastUser) return getMessageTimestamp(lastUser)
    const lastMessage = roomMessages[roomMessages.length - 1]
    return getMessageTimestamp(lastMessage)
  }
  const sortedRooms = [...rooms].sort(
    (a, b) => getLastQuestionTimestamp(b.id) - getLastQuestionTimestamp(a.id),
  )

  const isChatPage =
    typeof location?.pathname === "string" && location.pathname.startsWith("/assistant")

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages, isSending])

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

            <div className="flex items-center gap-3 mx-3">
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
                <Button variant="secondary" size="sm" className="h-8 px-3 text-xs" onClick={() => createRoom()}>
                  새 대화
                </Button>
              </div>
              <div className="flex items-center justify-between px-3 pb-2 border-b mb-2">


              </div>
              <div className="space-y-1 overflow-y-auto px-2 pb-3">
                {sortedRooms.map((room) => (
                  <Button
                    key={room.id}
                    variant={room.id === activeRoomId ? "secondary" : "ghost"}
                    size="sm"
                    className="w-full justify-between truncate"
                    onClick={() => selectRoom(room.id)}
                  >
                    <span className="truncate text-left text-sm">{room.name}</span>
                    {room.id === activeRoomId ? (
                      <span className="text-[10px] text-primary">현재</span>
                    ) : (
                      <span className="text-[10px] text-muted-foreground"></span>
                    )}
                  </Button>
                ))}
                {rooms.length === 0 && (
                  <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                    아직 대화방이 없습니다.
                  </div>
                )}
              </div>
            </aside>
          )}

          <div className="flex flex-1 flex-col overflow-hidden">

            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
              {messages.map((message) => {
                const isUser = message.role === "user"
                return (
                  <div
                    key={message.id}
                    className={["flex", isUser ? "justify-end" : "justify-start"].join(" ")}
                  >
                    <pre
                      className={[
                        "m-0 max-w-[80%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2 text-sm shadow-sm font-mono",
                        isUser
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-foreground",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {message.content}
                    </pre>
                  </div>
                )
              })}
              <AssistantStatusIndicator isSending={isSending} />
              <div ref={messagesEndRef} />
            </div>

            {errorMessage && (
              <div className="mx-4 shrink-0 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                <div className="flex items-center justify-between gap-2">
                  <span>{errorMessage}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 text-destructive underline underline-offset-4"
                    onClick={clearError}
                  >
                    닫기
                  </Button>
                </div>
              </div>
            )}

            <form
              onSubmit={handleSubmit}
              className="shrink-0 border-t bg-background px-3 pb-3 pt-2"
            >
              <label className="sr-only" htmlFor="chat-widget-input">
                어시스턴트에게 질문하기
              </label>
              <div className="flex items-end gap-2 rounded-xl border bg-muted/40 p-2">
                <textarea
                  id="chat-widget-input"
                  ref={inputRef}
                  className="min-h-[60px] flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed disabled:opacity-60"
                  placeholder="궁금한 점을 입력하세요. Shift+Enter로 줄바꿈"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault()
                      handleSubmit(event)
                    }
                  }}
                  disabled={isSending}
                />
                <Button
                  type="submit"
                  size="icon"
                  disabled={isSending || !input.trim()}
                  className="h-10 w-10 flex-none"
                >
                  {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  <span className="sr-only">Send message</span>
                </Button>
              </div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                <button
                  type="button"
                  className="text-primary underline underline-offset-4"
                  onClick={handleOpenFullChat}
                >
                  전체 화면에서 이어서 보기
                </button>
                <span>베타 · LLM API 연결</span>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div >
  )
}
