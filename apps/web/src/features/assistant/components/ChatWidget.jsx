import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"

import { resolveAssistantAppContext } from "../utils/appContext"
import { usePageAssistantContext } from "@/lib/assistant/pageContext"
import {
  isAssistantAppContextReady,
  resolveAssistantSurface,
} from "../utils/surfaceConfig"
import { useAuth } from "@/lib/auth"

import { ChatWidgetLauncher } from "./ChatWidgetLauncher"
import { ChatWidgetPanel } from "./ChatWidgetPanel"
import { useAttentionTooltip } from "../hooks/useAttentionTooltip"
import { useAssistantRagIndex } from "../hooks/useAssistantRagIndex"
import { useChatSession } from "../hooks/useChatSession"
import { useFloatingChatWindow } from "../hooks/useFloatingChatWindow"
import { sortRoomsByRecentQuestion } from "../utils/chatRooms"
import { ASSISTANT_KNOWLEDGE_MODES } from "../utils/profileKeys"
import { getAssistantKnowledgeCapability } from "../utils/knowledgeCapabilities"

export function ChatWidget(props) {
  const location = useLocation()
  const { pageContext } = usePageAssistantContext()
  const { user } = useAuth()
  const activeAppContext = resolveAssistantAppContext(location.pathname)
  const knowledgeCapability = getAssistantKnowledgeCapability(activeAppContext?.key)
  const [contextMode, setContextMode] = useState({
    appKey: activeAppContext?.key || "",
    knowledgeMode: knowledgeCapability.defaultMode,
  })
  const selectedKnowledgeMode = contextMode.appKey === activeAppContext?.key
    ? contextMode.knowledgeMode
    : knowledgeCapability.defaultMode
  const isAppContextReady = isAssistantAppContextReady({
    appKey: activeAppContext?.key,
    pageContext,
  })
  const effectiveKnowledgeMode = (
    selectedKnowledgeMode === ASSISTANT_KNOWLEDGE_MODES.currentApp
    && !isAppContextReady
  )
    ? ASSISTANT_KNOWLEDGE_MODES.auto
    : selectedKnowledgeMode

  useEffect(() => {
    setContextMode({
      appKey: activeAppContext?.key || "",
      knowledgeMode: knowledgeCapability.defaultMode,
    })
  }, [activeAppContext?.key, knowledgeCapability.defaultMode])

  const ragSettings = useAssistantRagIndex({
    enabled: Boolean(user) && (
      activeAppContext?.key === "emails"
      || effectiveKnowledgeMode === ASSISTANT_KNOWLEDGE_MODES.auto
    ),
  })
  const surface = resolveAssistantSurface({
    appKey: activeAppContext?.key,
    knowledgeMode: effectiveKnowledgeMode,
    pageContext,
    permissionGroups: ragSettings.permissionGroups,
    ragIndexNames: ragSettings.ragIndexNames,
  })

  const handleContextModeChange = (nextKnowledgeMode) => {
    setContextMode({
      appKey: activeAppContext?.key || "",
      knowledgeMode: nextKnowledgeMode,
    })
  }

  if (
    location.pathname.startsWith("/assistant") ||
    !user ||
    !activeAppContext ||
    !surface
  ) {
    return null
  }

  return (
    <ChatWidgetContent
      {...props}
      location={location}
      activeAppContext={activeAppContext}
      pageContext={
        ["emails", "observer", "line-dashboard"].includes(activeAppContext.key)
          ? pageContext
          : null
      }
      ragSettings={ragSettings}
      surface={surface}
      knowledgeMode={effectiveKnowledgeMode}
      supportsCurrentScope={knowledgeCapability.supportsCurrentScope}
      isAppContextReady={isAppContextReady}
      onKnowledgeModeChange={handleContextModeChange}
      user={user}
    />
  )
}

function ChatWidgetContent({
  availableMailboxes = [],
  location,
  activeAppContext,
  pageContext,
  ragSettings,
  surface,
  knowledgeMode,
  supportsCurrentScope,
  isAppContextReady,
  onKnowledgeModeChange,
  user,
}) {
  const [input, setInput] = useState("")
  const inputRef = useRef(null)
  const wasSendingRef = useRef(false)
  const {
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
    sidebarMaxWidth,
    sidebarMinWidth,
    sidebarWidth,
    size,
    toggleSidebar,
    widgetPosition,
  } = useFloatingChatWindow()
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
    errorMessage,
    canRetry,
    clearError,
    sendMessage,
    retryLastMessage,
    stopGenerating,
    selectRoom,
    searchRooms,
    loadMoreRooms,
    hasOlderMessages,
    isLoadingOlderMessages,
    loadOlderMessages,
    editUserMessage,
    regenerateAssistantMessage,
    rateAssistantMessage,
    createRoom,
    removeRoom,
    removeRooms,
    renameRoom,
    togglePinRoom,
    toggleArchiveRoom,
    toggleArchivedView,
    downloadConversation,
  } = useChatSession({
    messageContextKey: surface.appContextKey,
    profileKey: surface.profileKey,
    profileVersion: surface.profileVersion,
    profileToolInputs: surface.toolInputs,
    userKey: user.id,
  })
  const sortedRooms = sortRoomsByRecentQuestion(roomListRooms, messagesByRoom)
  const { isAttentionTooltipVisible, attentionTooltipText } = useAttentionTooltip({
    isOpen,
    isHomePage: location.pathname === "/",
  })

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      wasSendingRef.current = isSending
      return
    }
    if (!isSending && wasSendingRef.current) inputRef.current?.focus()
    wasSendingRef.current = isSending
  }, [isSending, isOpen])

  const focusInput = () => inputRef.current?.focus()

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!input.trim() || isSending) return
    try {
      const result = await sendMessage(input)
      if (result?.ok) setInput("")
    } finally {
      focusInput()
    }
  }

  const handleQuickPrompt = async () => {
    const prompt = pageContext?.defaultPrompt
    if (!prompt || isSending) return
    try {
      await sendMessage(prompt)
    } finally {
      focusInput()
    }
  }

  if (!isOpen) {
    return (
      <ChatWidgetLauncher
        buttonPosition={buttonPosition}
        onPointerDown={handleFloatingButtonPointerDown}
        onPointerMove={handleFloatingButtonPointerMove}
        onPointerUp={handleFloatingButtonPointerUp}
        onClick={handleFloatingButtonClick}
        floatingButtonRef={floatingButtonRef}
        isAttentionTooltipVisible={isAttentionTooltipVisible}
        attentionTooltipText={attentionTooltipText}
      />
    )
  }

  return (
    <ChatWidgetPanel
      containerRef={chatContainerRef}
      widgetPosition={widgetPosition}
      size={size}
      isMaximized={isMaximized}
      onResizePointerDown={handleResizePointerDown}
      onHeaderPointerDown={handleWidgetHeaderPointerDown}
      isSidebarOpen={isSidebarOpen}
      onToggleSidebar={toggleSidebar}
      sidebarWidth={sidebarWidth}
      sidebarMinWidth={sidebarMinWidth}
      sidebarMaxWidth={sidebarMaxWidth}
      onSidebarResizePointerDown={handleSidebarResizePointerDown}
      onSidebarResizeKeyDown={handleSidebarResizeKeyDown}
      ragSettings={ragSettings}
      rooms={rooms}
      sortedRooms={sortedRooms}
      activeRoomId={activeRoomId}
      onSelectRoom={selectRoom}
      onDeleteRoom={removeRoom}
      onDeleteRooms={removeRooms}
      onRenameRoom={renameRoom}
      onTogglePinRoom={togglePinRoom}
      onToggleArchiveRoom={toggleArchiveRoom}
      showArchived={showArchived}
      onToggleArchivedView={toggleArchivedView}
      onCreateRoom={createRoom}
      roomSearch={roomSearch}
      onSearchRooms={searchRooms}
      hasMoreRooms={hasMoreRooms}
      isLoadingMoreRooms={isLoadingMoreRooms}
      onLoadMoreRooms={loadMoreRooms}
      messages={messages}
      isSending={isSending}
      isGenerating={isGenerating}
      hasActiveGeneration={hasActiveGeneration}
      generationRoomId={generationRoomId}
      isRoomListBusy={isRoomListBusy}
      onStopGenerating={stopGenerating}
      hasOlderMessages={hasOlderMessages}
      isLoadingOlderMessages={isLoadingOlderMessages}
      onLoadOlderMessages={loadOlderMessages}
      onEditMessage={editUserMessage}
      onRegenerateMessage={regenerateAssistantMessage}
      onRateMessage={rateAssistantMessage}
      onDownloadConversation={downloadConversation}
      availableMailboxes={availableMailboxes}
      errorMessage={errorMessage}
      onClearError={clearError}
      canRetry={canRetry}
      onRetry={retryLastMessage}
      retryLabel="재시도"
      inputRef={inputRef}
      inputValue={input}
      onInputChange={(event) => setInput(event.target.value)}
      onSubmit={handleSubmit}
      onOpenFullChat={handleOpenFullChat}
      onRestoreDefaultSize={handleRestoreDefaultSize}
      onClose={closeWidget}
      pageContext={pageContext}
      activeAppContext={activeAppContext}
      knowledgeMode={knowledgeMode}
      supportsCurrentScope={supportsCurrentScope}
      isAppContextReady={isAppContextReady}
      onKnowledgeModeChange={onKnowledgeModeChange}
      usesEmailRag={activeAppContext.key === "emails" && surface.mode !== "portal"}
      onQuickPrompt={handleQuickPrompt}
      currentPageScope={pageContext?.scope || null}
    />
  )
}
