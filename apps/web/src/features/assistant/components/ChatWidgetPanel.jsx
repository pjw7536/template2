import { Minus, PanelLeft, SquareArrowOutUpRight } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

import { ChatComposer } from "./ChatComposer"
import { ChatErrorBanner } from "./ChatErrorBanner"
import { ChatMessages } from "./ChatMessages"
import { RoomList } from "./RoomList"

export function ChatWidgetPanel({
  containerRef,
  widgetPosition,
  size,
  onResizePointerDown,
  onHeaderPointerDown,
  isSidebarOpen,
  onToggleSidebar,
  ragIndex,
  rooms,
  sortedRooms,
  activeRoomId,
  onSelectRoom,
  onDeleteRoom,
  onCreateRoom,
  messages,
  isSending,
  errorMessage,
  onClearError,
  inputRef,
  inputValue,
  onInputChange,
  onSubmit,
  onOpenFullChat,
  onClose,
}) {
  const {
    userSdwtProd,
    setUserSdwtProd,
    options: userSdwtProdOptions,
    isLoading: isUserSdwtProdLoading,
    isError: isUserSdwtProdError,
    errorMessage: userSdwtProdErrorMessage,
    canSelect: canSelectUserSdwtProd,
  } = ragIndex

  return (
    <div
      ref={containerRef}
      className="fixed z-50"
      style={{
        left: widgetPosition.x,
        top: widgetPosition.y,
        width: size.width,
        maxWidth: "calc(100vw - 16px)",
      }}
    >
      <div
        className="relative flex max-h-[80vh] flex-col overflow-hidden rounded-xl border bg-card shadow-2xl"
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
          className="flex shrink-0 touch-none items-center justify-between border-b bg-card px-4 py-3 cursor-grab active:cursor-grabbing"
          onPointerDown={onHeaderPointerDown}
          role="presentation"
        >
          <div className="flex items-center gap-2">
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

            <div className="mx-3 flex items-center gap-3">
              <span className="flex h-2 w-2 rounded-full bg-primary ring-2 ring-primary/30" />
              <p className="text-sm font-semibold leading-tight">Etch AI Assistant</p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <div
              className="flex items-center gap-2 cursor-default"
              data-chat-widget-no-drag="true"
            >
              <span className="text-xs text-muted-foreground">지식</span>
              {canSelectUserSdwtProd ? (
                <Select value={userSdwtProd} onValueChange={setUserSdwtProd}>
                  <SelectTrigger
                    className="h-6 w-32 text-xs cursor-pointer"
                    aria-label="assistant 배경지식(user_sdwt_prod) 선택"
                  >
                    <SelectValue
                      placeholder={isUserSdwtProdLoading ? "불러오는 중" : "선택"}
                    />
                  </SelectTrigger>
                  <SelectContent data-chat-widget-portal="true">
                    {userSdwtProdOptions.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Badge
                  variant={isUserSdwtProdError ? "destructive" : "secondary"}
                  className="h-7 px-2 text-xs"
                  title={
                    isUserSdwtProdError
                      ? userSdwtProdErrorMessage || "분임조 목록을 불러오지 못했어요."
                      : userSdwtProd || undefined
                  }
                >
                  {userSdwtProd || (isUserSdwtProdLoading ? "…" : "—")}
                </Badge>
              )}
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onOpenFullChat}
              aria-label="Open full chat page"
            >
              <SquareArrowOutUpRight className="h-4 w-4" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onClose}
              aria-label="Minimize chat widget"
            >
              <Minus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {isSidebarOpen ? (
            <aside className="flex w-52 shrink-0 min-h-0 flex-col border-r bg-muted/40">
              <div className="flex items-center justify-between px-3 py-2">
                <div className="space-y-0.5">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">대화방</p>
                  <p className="text-sm font-semibold text-foreground">최근 {rooms.length}개</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={() => onCreateRoom()}
                >
                  새 대화
                </Button>
              </div>
              <div className="mb-2 flex items-center justify-between border-b px-3 pb-2" />
              <div className="flex-1 min-h-0 overflow-y-auto px-2 pb-3">
                <RoomList
                  rooms={sortedRooms}
                  activeRoomId={activeRoomId}
                  onSelectRoom={onSelectRoom}
                  onDeleteRoom={onDeleteRoom}
                />
              </div>
            </aside>
          ) : null}

          <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
            <ChatMessages messages={messages} isSending={isSending} fillBubbles />

            <ChatErrorBanner message={errorMessage} onDismiss={onClearError} />

            <ChatComposer
              inputId="chat-widget-input"
              label="어시스턴트에게 질문하기"
              inputRef={inputRef}
              inputValue={inputValue}
              onInputChange={onInputChange}
              onSubmit={onSubmit}
              isSending={isSending}
              placeholder="궁금한 점을 입력하세요. Shift+Enter로 줄바꿈"
              footerLeft={
                <button
                  type="button"
                  className="text-primary underline underline-offset-4"
                  onClick={onOpenFullChat}
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
