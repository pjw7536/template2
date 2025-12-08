import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { Bot, Loader2, PanelLeft, Plus, RefreshCw, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { AssistantStatusIndicator } from "../components/AssistantStatusIndicator"
import { useChatSession } from "../hooks/useChatSession"

export function ChatPage() {
  const location = useLocation()
  const handoffMessages = Array.isArray(location?.state?.initialMessages)
    ? location.state.initialMessages
    : undefined
  const initialRooms = Array.isArray(location?.state?.initialRooms)
    ? location.state.initialRooms
    : undefined
  const initialMessagesByRoom =
    location?.state?.initialMessagesByRoom && typeof location.state.initialMessagesByRoom === "object"
      ? location.state.initialMessagesByRoom
      : undefined
  const initialActiveRoomId =
    typeof location?.state?.initialActiveRoomId === "string"
      ? location.state.initialActiveRoomId
      : undefined

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
  } = useChatSession({
    initialMessages: handoffMessages,
    initialRooms,
    initialMessagesByRoom,
    initialActiveRoomId,
  })

  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [input, setInput] = useState("")
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isSending])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim() || isSending) return
    try {
      await sendMessage(input)
      setInput("")
    } finally {
      inputRef.current?.focus()
    }
  }

  return (
    <div className="mx-auto flex max-w-8xl flex-col gap-4 px-4 py-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">Etch AI Assistant</p>
            <p className="text-xs text-muted-foreground">Etch기술팀 AI Chatbot 입니다.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex h-2 w-2 rounded-full bg-primary ring-2 ring-primary/30" />
          <span>현재 대화방: {activeRoom.name}</span>
        </div>
      </header>

      <div className="flex h-[720px] max-h-[80vh] flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b bg-card px-4 py-3">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={isSidebarOpen ? "secondary" : "outline"}
              size="icon"
              className="h-9 w-9"
              onClick={() => setIsSidebarOpen((prev) => !prev)}
              aria-label={isSidebarOpen ? "대화방 목록 닫기" : "대화방 목록 열기"}
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-3">
              <span className="flex h-2 w-2 rounded-full bg-primary ring-2 ring-primary/30" />
              <p className="text-sm font-semibold leading-tight">Etch AI Assistant</p>
              <span className="text-xs text-muted-foreground">실시간 상담</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={() => createRoom()}
              aria-label="새 대화방 만들기"
            >
              <Plus className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              onClick={() => resetConversation(activeRoomId)}
              disabled={isSending}
              aria-label="현재 대화 초기화"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {isSidebarOpen && (
            <aside className="flex w-64 shrink-0 flex-col border-r bg-muted/40">
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
              <div className="mb-2 flex items-center justify-between border-b px-3 pb-2">
                <span className="text-[11px] text-muted-foreground">방을 선택하세요</span>
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
                      <span className="text-[10px] text-muted-foreground" />
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
                    <div
                      className={[
                        "max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm",
                        isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                    >
                      {message.content}
                    </div>
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
              <label className="sr-only" htmlFor="assistant-page-input">
                어시스턴트에게 질문하기
              </label>
              <div className="flex items-end gap-2 rounded-xl border bg-muted/40 p-2">
                <textarea
                  id="assistant-page-input"
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
                <span>베타 · LLM API 연결</span>
                <span>Shift+Enter로 줄바꿈</span>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
