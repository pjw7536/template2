import { useEffect, useState } from "react"
import { Database, Download, Maximize, Minimize2, Minus, PanelLeft, Settings, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import { ChatComposer } from "./ChatComposer"
import { ChatContextModeSelector, ChatKnowledgeToggle } from "./ChatContextModeSelector"
import { ChatErrorBanner } from "./ChatErrorBanner"
import { ChatMessages } from "./ChatMessages"
import { RoomList } from "./RoomList"
import { RagIndexMultiSelect } from "./RagIndexMultiSelect"

export function ChatWidgetPanel({
  containerRef,
  widgetPosition,
  size,
  isMaximized,
  onResizePointerDown,
  onHeaderPointerDown,
  isSidebarOpen,
  onToggleSidebar,
  sidebarWidth,
  sidebarMinWidth,
  sidebarMaxWidth,
  onSidebarResizePointerDown,
  onSidebarResizeKeyDown,
  ragSettings,
  rooms,
  sortedRooms,
  activeRoomId,
  onSelectRoom,
  onDeleteRoom,
  onDeleteRooms,
  onRenameRoom,
  onTogglePinRoom,
  onToggleArchiveRoom,
  showArchived,
  onToggleArchivedView,
  onCreateRoom,
  roomSearch,
  onSearchRooms,
  hasMoreRooms,
  isLoadingMoreRooms,
  onLoadMoreRooms,
  messages,
  isSending,
  isGenerating,
  hasActiveGeneration,
  generationRoomId,
  isRoomListBusy,
  onStopGenerating,
  hasOlderMessages,
  isLoadingOlderMessages,
  onLoadOlderMessages,
  onEditMessage,
  onRegenerateMessage,
  onRateMessage,
  onDownloadConversation,
  availableMailboxes = [],
  errorMessage,
  onClearError,
  canRetry,
  onRetry,
  retryLabel,
  canDiscard,
  onDiscard,
  inputRef,
  inputValue,
  onInputChange,
  onSubmit,
  onOpenFullChat,
  onRestoreDefaultSize,
  onClose,
  pageContext,
  activeAppContext,
  knowledgeMode,
  supportsCurrentScope,
  isAppContextReady,
  onKnowledgeModeChange,
  usesEmailRag,
  onQuickPrompt,
  currentPageScope,
}) {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const {
    permissionGroups,
    setPermissionGroups,
    ragIndexNames,
    setRagIndexNames,
    permissionGroupOptions,
    ragIndexOptions,
    isLoading: isRagSettingsLoading,
    isError: isRagSettingsError,
    errorMessage: ragSettingsErrorMessage,
  } = ragSettings
  const showRagSettings = usesEmailRag && !pageContext
  const statusMode = pageContext?.kind === "observer" ? "observer" : usesEmailRag ? "email" : "openwebui"

  useEffect(() => {
    if (!showRagSettings) setIsSettingsOpen(false)
  }, [showRagSettings])

  const handleSelectRoom = (roomId) => {
    setIsSettingsOpen(false)
    onSelectRoom(roomId)
  }

  const handleCreateRoom = () => {
    setIsSettingsOpen(false)
    onCreateRoom()
  }

  const handleToggleSettings = () => {
    setIsSettingsOpen((prev) => !prev)
  }

  return (
    <div
      ref={containerRef}
      className="fixed z-50"
      role="dialog"
      aria-modal="false"
      aria-label="Etch AI Assistant"
      style={{
        left: widgetPosition.x,
        top: widgetPosition.y,
        width: size.width,
        maxWidth: isMaximized ? "100vw" : "calc(100vw - 16px)",
      }}
    >
      <div
        className={`relative flex flex-col overflow-hidden rounded-xl border bg-card shadow-2xl ${isMaximized ? "max-h-none" : "max-h-[80vh]"
          }`}
        style={{ height: size.height }}
      >
        <div className="pointer-events-none absolute inset-0">
          <div
            className="absolute inset-y-0 left-0 w-2 cursor-ew-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("w")}
            role="presentation"
          />
          <div
            className="absolute inset-y-0 right-0 w-2 cursor-ew-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("e")}
            role="presentation"
          />
          <div
            className="absolute inset-x-0 top-0 h-2 cursor-ns-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("n")}
            role="presentation"
          />
          <div
            className="absolute inset-x-0 bottom-0 h-2 cursor-ns-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("s")}
            role="presentation"
          />
          <div
            className="absolute left-0 top-0 h-3 w-3 cursor-nwse-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("nw")}
            role="presentation"
          />
          <div
            className="absolute right-0 top-0 h-3 w-3 cursor-nesw-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("ne")}
            role="presentation"
          />
          <div
            className="absolute bottom-0 left-0 h-3 w-3 cursor-nesw-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("sw")}
            role="presentation"
          />
          <div
            className="absolute bottom-0 right-0 h-3 w-3 cursor-nwse-resize pointer-events-auto"
            onPointerDown={onResizePointerDown("se")}
            role="presentation"
          />
        </div>

        <div
          className="flex shrink-0 touch-none flex-col gap-2 border-b bg-card px-4 py-3 cursor-grab active:cursor-grabbing"
          onPointerDown={onHeaderPointerDown}
          role="presentation"
        >
          <div className="flex h-8 items-center justify-between">
            <div className="flex h-8 min-w-0 items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={onToggleSidebar}
                aria-label={isSidebarOpen ? "대화방 목록 닫기" : "대화방 목록 열기"}
              >
                <PanelLeft className="h-3 w-3" />
              </Button>

              <div className="mx-3 flex h-8 min-w-0 items-center gap-2">
                <span className="flex h-2 w-2 rounded-full bg-primary ring-2 ring-primary/30" />
                <p className="flex h-8 items-center truncate text-sm font-semibold leading-tight">
                  Etch AI Assistant
                </p>
              </div>
            </div>

            <div className="flex h-8 items-center gap-1">
              {supportsCurrentScope ? (
                <ChatContextModeSelector
                  appLabel={activeAppContext.label}
                  mode={knowledgeMode}
                  onChange={onKnowledgeModeChange}
                  disabled={isSending}
                  currentAppReady={isAppContextReady}
                  disabledReason={
                    !isAppContextReady
                      ? `${activeAppContext.label} 조회 조건이 준비되면 사용할 수 있습니다.`
                      : ""
                  }
                />
              ) : (
                <ChatKnowledgeToggle
                  checked={knowledgeMode === "auto"}
                  onChange={onKnowledgeModeChange}
                  disabled={isSending}
                />
              )}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    disabled={!activeRoomId}
                    aria-label="대화 내보내기"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" data-chat-widget-portal="true">
                  <DropdownMenuItem onSelect={() => onDownloadConversation?.("markdown")}>
                    Markdown으로 저장
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => onDownloadConversation?.("csv")}>
                    Excel용 CSV로 저장
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              {!isMaximized ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onOpenFullChat}
                  aria-label="전체 화면으로 보기"
                >
                  <Maximize className="h-4 w-4" />
                </Button>
              ) : null}

              {isMaximized ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={onRestoreDefaultSize}
                  aria-label="작게 보기"
                >
                  <Minimize2 className="h-4 w-4" />
                </Button>
              ) : null}

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={onClose}
                aria-label="채팅 위젯 최소화"
              >
                <Minus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="grid gap-2" data-chat-widget-no-drag="true">
            {pageContext ? (
              <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                <Database className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-foreground">
                    {pageContext.label || "현재 화면 데이터 연결됨"}
                  </p>
                  {pageContext.description ? (
                    <p className="truncate text-[11px] text-muted-foreground">
                      {pageContext.description}
                    </p>
                  ) : null}
                </div>
                {pageContext.defaultPrompt ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="h-7 shrink-0 px-2 text-xs"
                    disabled={isSending}
                    onClick={onQuickPrompt}
                  >
                    <Sparkles className="size-3.5" aria-hidden="true" />
                    종합 분석
                  </Button>
                ) : null}
              </div>
            ) : showRagSettings ? (
              <>
                <div className="grid gap-2 sm:grid-cols-2">
                  <RagIndexMultiSelect
                    label="RAG 인덱스"
                    values={ragIndexNames}
                    onChange={setRagIndexNames}
                    placeholder="rp-unclassified"
                    options={ragIndexOptions}
                    isDisabled={isRagSettingsLoading}
                    showSelectionBadges={false}
                  />
                  <RagIndexMultiSelect
                    label="권한 그룹"
                    values={permissionGroups}
                    onChange={setPermissionGroups}
                    placeholder="rag-public"
                    options={permissionGroupOptions}
                    isDisabled={isRagSettingsLoading}
                    showSelectionBadges={false}
                  />
                </div>
                {isRagSettingsError ? (
                  <p className="text-[11px] text-destructive">
                    {ragSettingsErrorMessage || "RAG 설정을 불러오지 못했어요."}
                  </p>
                ) : null}
              </>
            ) : activeAppContext?.key && supportsCurrentScope ? (
              <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                <Database className="size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-foreground">
                    {knowledgeMode === "auto"
                      ? "자동 지식 선택"
                      : `${activeAppContext.label} 지식만 사용`}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {knowledgeMode === "auto"
                      ? "질문에 맞는 접근 가능한 업무 지식을 자동으로 선택합니다."
                      : activeAppContext.description}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {isSidebarOpen ? (
            <aside
              className="relative flex shrink-0 min-h-0 flex-col border-r bg-muted/40"
              style={{ width: sidebarWidth }}
            >
              <div
                className="absolute inset-y-0 right-0 z-10 w-2 translate-x-1/2 touch-none cursor-col-resize outline-none after:absolute after:inset-y-0 after:left-1/2 after:w-px after:-translate-x-1/2 after:bg-transparent hover:after:bg-primary/50 focus-visible:after:w-0.5 focus-visible:after:bg-primary"
                role="separator"
                aria-label="대화방 목록 너비 조절"
                aria-orientation="vertical"
                aria-valuemin={sidebarMinWidth}
                aria-valuemax={sidebarMaxWidth}
                aria-valuenow={Math.round(sidebarWidth)}
                tabIndex={0}
                onPointerDown={onSidebarResizePointerDown}
                onKeyDown={onSidebarResizeKeyDown}
              />
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
              <div className="mb-2 flex items-center justify-between border-b px-3 pb-2" />
              <div className="flex-1 min-h-0 overflow-y-auto px-2 pb-3">
                <RoomList
                  rooms={sortedRooms}
                  activeRoomId={activeRoomId}
                  onSelectRoom={handleSelectRoom}
                  onDeleteRoom={onDeleteRoom}
                  onDeleteRooms={onDeleteRooms}
                  onRenameRoom={onRenameRoom}
                  onTogglePinRoom={onTogglePinRoom}
                  onToggleArchiveRoom={onToggleArchiveRoom}
                  showArchived={showArchived}
                  onToggleArchivedView={onToggleArchivedView}
                  isDisabled={isRoomListBusy}
                  disabledRoomIds={generationRoomId ? [generationRoomId] : []}
                  searchValue={roomSearch}
                  onSearchRooms={onSearchRooms}
                  hasMore={hasMoreRooms}
                  isLoadingMore={isLoadingMoreRooms}
                  onLoadMore={onLoadMoreRooms}
                />
              </div>
              {showRagSettings ? (
                <div className="border-t px-3 py-3">
                  <Button
                    variant={isSettingsOpen ? "secondary" : "outline"}
                    size="sm"
                    className="h-9 w-full justify-between"
                    onClick={handleToggleSettings}
                    disabled={isSending}
                  >
                    <span className="text-xs font-semibold">설정</span>
                    <Settings className="h-4 w-4" />
                  </Button>
                </div>
              ) : null}
            </aside>
          ) : null}

          <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
            {isSettingsOpen && showRagSettings ? (
              <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
                <div className="flex items-center gap-2 border-b px-4 py-3">
                  <Settings className="h-4 w-4 text-muted-foreground" />
                  <p className="text-sm font-semibold">RAG 설정</p>
                </div>
                <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3">
                  <div className="grid gap-3">
                    <RagIndexMultiSelect
                      label="RAG 인덱스"
                      values={ragIndexNames}
                      onChange={setRagIndexNames}
                      placeholder="rp-unclassified"
                      helperText="목록에서 선택 · 최소 1개 필수"
                      options={ragIndexOptions}
                      isDisabled={isRagSettingsLoading}
                    />
                    <RagIndexMultiSelect
                      label="권한 그룹"
                      values={permissionGroups}
                      onChange={setPermissionGroups}
                      placeholder="rag-public"
                      helperText="목록에서 선택 · 최소 1개 필수"
                      options={permissionGroupOptions}
                      isDisabled={isRagSettingsLoading}
                    />
                    {isRagSettingsError ? (
                      <p className="text-[11px] text-destructive">
                        {ragSettingsErrorMessage || "RAG 설정을 불러오지 못했어요."}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <ChatMessages
                  messages={messages}
                  conversationKey={activeRoomId}
                  isGenerating={isGenerating}
                  isActionDisabled={hasActiveGeneration}
                  fillBubbles
                  availableMailboxes={availableMailboxes}
                  statusMode={statusMode}
                  hasOlderMessages={hasOlderMessages}
                  isLoadingOlderMessages={isLoadingOlderMessages}
                  onLoadOlderMessages={onLoadOlderMessages}
                  onEditMessage={onEditMessage}
                  onRegenerateMessage={onRegenerateMessage}
                  onRateMessage={onRateMessage}
                  currentPageScope={currentPageScope}
                />

                <ChatErrorBanner
                  message={errorMessage}
                  onDismiss={onClearError}
                  canRetry={canRetry}
                  onRetry={onRetry}
                  retryLabel={retryLabel}
                  canDiscard={canDiscard}
                  onDiscard={onDiscard}
                />

                <ChatComposer
                  inputId="chat-widget-input"
                  label="어시스턴트에게 질문하기"
                  inputRef={inputRef}
                  inputValue={inputValue}
                  onInputChange={onInputChange}
                  onSubmit={onSubmit}
                  isSending={isSending}
                  isGenerating={isGenerating}
                  onStop={onStopGenerating}
                  placeholder={
                    pageContext?.placeholder || "궁금한 점을 입력하세요. Shift+Enter로 줄바꿈"
                  }
                  footerRight={
                    pageContext?.footer ||
                    (usesEmailRag ? "메일 RAG · LLM API 연결" : "GPT-OSS-120B")
                  }
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
