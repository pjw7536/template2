import { useEffect, useRef, useState } from "react"
import { useLocation, useOutletContext } from "react-router-dom"
import { Bot, Download, PanelLeft, Plus, RefreshCw, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth"
import { sendOpenWebUIStreamingMessage } from "../api/sendChatMessage"
import { ChatComposer } from "../components/ChatComposer"
import { ChatErrorBanner } from "../components/ChatErrorBanner"
import { ChatMessages } from "../components/ChatMessages"
import { RoomList } from "../components/RoomList"
import { useChatSession } from "../hooks/useChatSession"
import { sortRoomsByRecentQuestion } from "../utils/chatRooms"

export function ChatPage() {
  const { user } = useAuth()
  const location = useLocation()
  const outletContext = useOutletContext() || {}
  const availableMailboxes = Array.isArray(outletContext.availableMailboxes)
    ? outletContext.availableMailboxes
    : []
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
    roomListRooms,
    roomSearch,
    showArchived,
    hasMoreRooms,
    isLoadingMoreRooms,
    activeRoomId,
    messages,
    messagesByRoom,
    isSending,
    isGenerating,
    hasActiveGeneration,
    generationRoomId,
    isRoomListBusy,
    isSessionLoading,
    errorMessage,
    canRetry,
    canRetrySave,
    clearError,
    sendMessage,
    retryAssistantSave,
    discardFailedAssistantSave,
    retryLastMessage,
    stopGenerating,
    resetConversation,
    editUserMessage,
    regenerateAssistantMessage,
    rateAssistantMessage,
    selectRoom,
    searchRooms,
    loadMoreRooms,
    hasOlderMessages,
    isLoadingOlderMessages,
    loadOlderMessages,
    createRoom,
    removeRoom,
    removeRooms,
    renameRoom,
    togglePinRoom,
    toggleArchiveRoom,
    toggleArchivedView,
    downloadConversation,
  } = useChatSession({
    initialMessages: handoffMessages,
    initialRooms,
    initialMessagesByRoom,
    initialActiveRoomId,
    messageSender: sendOpenWebUIStreamingMessage,
    messageContextKey: "assistant:openwebui",
    userKey: user?.id,
  })

  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [input, setInput] = useState("")
  const inputRef = useRef(null)
  const wasSendingRef = useRef(false)
  const activeRoom = rooms.find((room) => room.id === activeRoomId) || rooms[0] || { name: "대화방" }

  const sortedRooms = sortRoomsByRecentQuestion(roomListRooms, messagesByRoom)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!isSending && wasSendingRef.current && inputRef.current) {
      inputRef.current.focus()
    }
    wasSendingRef.current = isSending
  }, [isSending])

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim() || isSending) return
    try {
      const result = await sendMessage(input)
      if (result?.ok) setInput("")
    } finally {
      inputRef.current?.focus()
    }
  }

  const handleDeleteRoom = (roomId) => {
    removeRoom(roomId)
  }

  const handleDeleteRooms = (roomIds) => removeRooms(roomIds)

  const handleSelectRoom = (roomId) => {
    selectRoom(roomId)
  }

  const handleCreateRoom = () => {
    if (isSessionLoading) return
    createRoom()
  }

  const handleResetConversation = () => {
    resetConversation(activeRoomId)
  }

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-4 overflow-hidden">
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

      <div className="grid min-h-0 grid-rows-[auto_1fr] gap-3 rounded-xl border bg-card shadow-sm">
        <div className="flex flex-col gap-2 border-b bg-card px-4 py-3">
          <div className="flex items-center justify-between">
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
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9"
                    disabled={!activeRoomId}
                    aria-label="대화 내보내기"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => downloadConversation("markdown")}>
                    Markdown으로 저장
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => downloadConversation("csv")}>
                    Excel용 CSV로 저장
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={handleCreateRoom}
                disabled={isRoomListBusy}
                aria-label="새 대화방 만들기"
              >
                <Plus className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={handleResetConversation}
                disabled={isSending}
                aria-label="현재 대화 초기화"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <Sparkles className="size-3.5 text-primary" aria-hidden="true" />
            <Badge variant="secondary" className="text-[11px]">
              OpenWebUI
            </Badge>
            <span>일반 대화 모드</span>
          </div>
        </div>

        <div className="grid min-h-0 grid-cols-1 overflow-hidden lg:grid-cols-[280px_1fr]">
          {isSidebarOpen ? (
            <aside className="flex min-h-0 flex-col border-r bg-muted/40">
              <div className="flex items-center justify-between px-3 py-2">
                <div className="space-y-0.5">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">대화방</p>
                  <p className="text-sm font-semibold text-foreground">
                    {showArchived ? "보관" : "최근"} {rooms.length}개
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={handleCreateRoom}
                  disabled={isRoomListBusy}
                >
                  새 대화
                </Button>
              </div>
              <div className="mb-2 flex items-center justify-between border-b px-3 pb-2">
                <span className="text-[11px] text-muted-foreground">방을 선택하세요</span>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto px-2 pb-3">
                <RoomList
                  rooms={sortedRooms}
                  activeRoomId={activeRoomId}
                  onSelectRoom={handleSelectRoom}
                  onDeleteRoom={handleDeleteRoom}
                  onDeleteRooms={handleDeleteRooms}
                  onRenameRoom={renameRoom}
                  onTogglePinRoom={togglePinRoom}
                  onToggleArchiveRoom={toggleArchiveRoom}
                  showArchived={showArchived}
                  onToggleArchivedView={toggleArchivedView}
                  isDisabled={isRoomListBusy}
                  disabledRoomIds={generationRoomId ? [generationRoomId] : []}
                  searchValue={roomSearch}
                  onSearchRooms={searchRooms}
                  hasMore={hasMoreRooms}
                  isLoadingMore={isLoadingMoreRooms}
                  onLoadMore={loadMoreRooms}
                />
              </div>
            </aside>
          ) : null}

          <div className="flex min-h-0 flex-col">
            <ChatMessages
              messages={messages}
              conversationKey={activeRoomId}
              isGenerating={isGenerating}
              isActionDisabled={hasActiveGeneration}
              availableMailboxes={availableMailboxes}
              statusMode="openwebui"
              hasOlderMessages={hasOlderMessages}
              isLoadingOlderMessages={isLoadingOlderMessages}
              onLoadOlderMessages={loadOlderMessages}
              onEditMessage={editUserMessage}
              onRegenerateMessage={regenerateAssistantMessage}
              onRateMessage={rateAssistantMessage}
            />

            <ChatErrorBanner
              message={errorMessage}
              onDismiss={clearError}
              canRetry={canRetrySave || canRetry}
              onRetry={canRetrySave ? retryAssistantSave : retryLastMessage}
              retryLabel={canRetrySave ? "답변 저장 다시 시도" : "재시도"}
              canDiscard={canRetrySave}
              onDiscard={discardFailedAssistantSave}
            />

            <ChatComposer
              inputId="assistant-page-input"
              label="어시스턴트에게 질문하기"
              inputRef={inputRef}
              inputValue={input}
              onInputChange={(event) => setInput(event.target.value)}
              onSubmit={handleSubmit}
              isSending={isSending}
              isGenerating={isGenerating}
              onStop={stopGenerating}
              placeholder="궁금한 점을 입력하세요. Shift+Enter로 줄바꿈"
              footerLeft="OpenWebUI 연결"
              footerRight="Shift+Enter로 줄바꿈"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
