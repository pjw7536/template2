import { useEffect, useRef, useState } from "react"
import {
  Archive,
  ArchiveRestore,
  Loader2,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Search,
  ListChecks,
  Trash2,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

function RoomSelectButton({
  room,
  isActive,
  isGenerating,
  isBatchSelected,
  isSelectionMode,
  onSelectRoom,
  onToggleSelection,
  isDisabled,
}) {
  const titleRef = useRef(null)
  const [isTooltipOpen, setIsTooltipOpen] = useState(false)

  const handleTooltipOpenChange = (nextOpen) => {
    const titleElement = titleRef.current
    const isOverflowing =
      titleElement && titleElement.scrollWidth > titleElement.clientWidth

    setIsTooltipOpen(Boolean(nextOpen && isOverflowing))
  }

  return (
    <Tooltip open={isTooltipOpen} onOpenChange={handleTooltipOpenChange}>
      <TooltipTrigger asChild>
        <Button
          variant={isBatchSelected || isActive ? "secondary" : "ghost"}
          size="sm"
          className="min-w-0 flex-1 justify-between"
          onClick={() =>
            isSelectionMode ? onToggleSelection?.(room.id) : onSelectRoom?.(room.id)
          }
          disabled={isDisabled}
          aria-pressed={isSelectionMode ? isBatchSelected : undefined}
        >
          <span ref={titleRef} className="min-w-0 flex-1 truncate text-left text-sm">
            {room.name}
          </span>
          {room.pinned && !isGenerating ? (
            <Pin className="size-3 shrink-0 text-primary" aria-hidden="true" />
          ) : null}
          {isGenerating ? (
            <span className="flex shrink-0 items-center gap-1 text-[10px] text-primary">
              <Loader2 className="size-3 animate-spin" />
              생성 중
            </span>
          ) : isActive ? (
            <span className="shrink-0 text-[10px] text-primary">현재</span>
          ) : null}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right" sideOffset={6} className="max-w-72 break-words">
        {room.name}
      </TooltipContent>
    </Tooltip>
  )
}

export function RoomList({
  rooms = [],
  activeRoomId,
  onSelectRoom,
  onDeleteRoom,
  onDeleteRooms,
  onRenameRoom,
  onTogglePinRoom,
  onToggleArchiveRoom,
  showArchived = false,
  onToggleArchivedView,
  isDisabled = false,
  disabledRoomIds = [],
  searchValue = "",
  onSearchRooms,
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
}) {
  const hasRooms = Array.isArray(rooms) && rooms.length > 0
  const [searchInput, setSearchInput] = useState(searchValue)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [isSelectionMode, setIsSelectionMode] = useState(false)
  const [selectedRoomIds, setSelectedRoomIds] = useState(() => new Set())
  const [isBulkDeleteOpen, setIsBulkDeleteOpen] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  const [renameTarget, setRenameTarget] = useState(null)
  const [renameValue, setRenameValue] = useState("")
  const [isRenaming, setIsRenaming] = useState(false)
  const lastRequestedSearchRef = useRef(searchValue)
  const disabledRoomIdSet = new Set(disabledRoomIds)
  const selectableRoomIds = rooms
    .map((room) => room.id)
    .filter((roomId) => !disabledRoomIdSet.has(roomId))
  const allSelectableRoomsSelected =
    selectableRoomIds.length > 0 &&
    selectableRoomIds.every((roomId) => selectedRoomIds.has(roomId))

  useEffect(() => {
    lastRequestedSearchRef.current = searchValue
    setSearchInput(searchValue)
  }, [searchValue])

  useEffect(() => {
    if (searchInput === lastRequestedSearchRef.current) return
    const timeoutId = window.setTimeout(() => onSearchRooms?.(searchInput), 250)
    lastRequestedSearchRef.current = searchInput
    return () => window.clearTimeout(timeoutId)
  }, [onSearchRooms, searchInput])

  useEffect(() => {
    const visibleRoomIdSet = new Set(rooms.map((room) => room.id))
    const disabledIdSet = new Set(disabledRoomIds)
    setSelectedRoomIds((previous) => {
      const next = new Set(
        Array.from(previous).filter(
          (roomId) => visibleRoomIdSet.has(roomId) && !disabledIdSet.has(roomId),
        ),
      )
      return next.size === previous.size ? previous : next
    })
  }, [rooms, disabledRoomIds])

  useEffect(() => {
    setIsSelectionMode(false)
    setSelectedRoomIds(new Set())
    setIsBulkDeleteOpen(false)
  }, [searchValue, showArchived])

  const toggleRoomSelection = (roomId) => {
    if (disabledRoomIdSet.has(roomId)) return
    setSelectedRoomIds((previous) => {
      const next = new Set(previous)
      if (next.has(roomId)) next.delete(roomId)
      else next.add(roomId)
      return next
    })
  }

  const toggleAllRooms = () => {
    setSelectedRoomIds(
      allSelectableRoomsSelected ? new Set() : new Set(selectableRoomIds),
    )
  }

  const exitSelectionMode = () => {
    setIsSelectionMode(false)
    setSelectedRoomIds(new Set())
    setIsBulkDeleteOpen(false)
  }

  const confirmBulkDelete = async () => {
    const targetIds = Array.from(selectedRoomIds)
    if (!targetIds.length || isBulkDeleting) return
    setIsBulkDeleting(true)
    try {
      const result = await onDeleteRooms?.(targetIds)
      const deletedIds = new Set(
        Array.isArray(result?.deletedIds) ? result.deletedIds : targetIds,
      )
      const failedIds = targetIds.filter((roomId) => !deletedIds.has(roomId))
      setSelectedRoomIds(new Set(failedIds))
      setIsBulkDeleteOpen(false)
      if (!failedIds.length) setIsSelectionMode(false)
    } finally {
      setIsBulkDeleting(false)
    }
  }

  return (
    <div className="space-y-2">
      {onSearchRooms ? (
        <div className="flex gap-1">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={showArchived ? "보관 대화 검색" : "대화방 검색"}
              aria-label={showArchived ? "보관 대화 검색" : "대화방 검색"}
              className="h-8 pl-8 text-xs"
            />
          </div>
          <Button
            type="button"
            variant={showArchived ? "secondary" : "ghost"}
            size="icon"
            className="size-8 shrink-0"
            onClick={onToggleArchivedView}
            aria-label={showArchived ? "최근 대화 보기" : "보관된 대화 보기"}
          >
            {showArchived ? <ArchiveRestore className="size-4" /> : <Archive className="size-4" />}
          </Button>
        </div>
      ) : null}
      {hasRooms && onDeleteRooms ? (
        isSelectionMode ? (
          <div className="flex h-9 items-center gap-1.5 rounded-md border bg-muted/40 px-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 shrink-0 px-2 text-xs leading-none"
              onClick={toggleAllRooms}
              disabled={isDisabled || !selectableRoomIds.length}
            >
              {allSelectableRoomsSelected ? "전체 해제" : "전체 선택"}
            </Button>
            <span className="mr-auto inline-flex h-7 items-center whitespace-nowrap text-[11px] leading-none text-muted-foreground">
              {selectedRoomIds.size}개 선택
            </span>
            <Button
              type="button"
              variant="destructive"
              size="icon"
              className="size-7 shrink-0"
              onClick={() => setIsBulkDeleteOpen(true)}
              disabled={isDisabled || !selectedRoomIds.size}
              aria-label="삭제"
            >
              <Trash2 className="size-3.5" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={exitSelectionMode}
              disabled={isDisabled}
              aria-label="대화방 선택 취소"
            >
              <X className="size-3.5" />
            </Button>
          </div>
        ) : (
          <div className="flex h-9 items-center justify-end">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground"
              onClick={() => setIsSelectionMode(true)}
              disabled={isDisabled}
            >
              <ListChecks className="size-3.5" />
              선택
            </Button>
          </div>
        )
      ) : null}
      {hasRooms &&
        rooms.map((room) => (
          <div key={room.id} className="flex items-center gap-2">
            {isSelectionMode ? (
              <Checkbox
                checked={selectedRoomIds.has(room.id)}
                onCheckedChange={() => toggleRoomSelection(room.id)}
                disabled={isDisabled || disabledRoomIdSet.has(room.id)}
                aria-label={`${room.name} 선택`}
              />
            ) : null}
            <RoomSelectButton
              room={room}
              isActive={room.id === activeRoomId}
              isGenerating={disabledRoomIdSet.has(room.id)}
              isBatchSelected={selectedRoomIds.has(room.id)}
              isSelectionMode={isSelectionMode}
              onSelectRoom={onSelectRoom}
              onToggleSelection={toggleRoomSelection}
              isDisabled={
                isDisabled || (isSelectionMode && disabledRoomIdSet.has(room.id))
              }
            />
            {!isSelectionMode ? <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-muted-foreground"
                  disabled={isDisabled || disabledRoomIdSet.has(room.id)}
                  aria-label={`${room.name} 메뉴`}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                data-chat-widget-portal="true"
                className="w-40"
              >
                {!showArchived ? (
                  <DropdownMenuItem onSelect={() => onTogglePinRoom?.(room.id)}>
                    {room.pinned ? <PinOff /> : <Pin />}
                    {room.pinned ? "고정 해제" : "상단 고정"}
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuItem
                  onSelect={() => {
                    setRenameTarget(room)
                    setRenameValue(room.name)
                  }}
                >
                  <Pencil /> 이름 변경
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onToggleArchiveRoom?.(room.id)}>
                  {showArchived ? <ArchiveRestore /> : <Archive />}
                  {showArchived ? "보관 해제" : "보관"}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setDeleteTarget(room)}>
                  <Trash2 /> 삭제
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu> : null}
          </div>
        ))}

      {!hasRooms && (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          {searchInput ? "검색 결과가 없습니다." : "아직 대화방이 없습니다."}
        </div>
      )}

      {hasMore ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full text-xs text-muted-foreground"
          onClick={onLoadMore}
          disabled={isLoadingMore}
        >
          {isLoadingMore ? <Loader2 className="size-3.5 animate-spin" /> : null}
          더 불러오기
        </Button>
      ) : null}

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent data-chat-widget-portal="true" className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>대화방을 삭제할까요?</DialogTitle>
            <DialogDescription>
              “{deleteTarget?.name}”의 모든 대화 내용이 삭제되며 복구할 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">취소</Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                onDeleteRoom?.(deleteTarget?.id)
                setDeleteTarget(null)
              }}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isBulkDeleteOpen} onOpenChange={(open) => !isBulkDeleting && setIsBulkDeleteOpen(open)}>
        <DialogContent data-chat-widget-portal="true" className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>선택한 대화방을 삭제할까요?</DialogTitle>
            <DialogDescription>
              선택한 {selectedRoomIds.size}개 대화방과 모든 대화 내용이 삭제되며 복구할 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isBulkDeleting}>취소</Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              onClick={confirmBulkDelete}
              disabled={isBulkDeleting || !selectedRoomIds.size}
            >
              {isBulkDeleting ? <Loader2 className="size-4 animate-spin" /> : null}
              {isBulkDeleting ? "삭제 중" : `${selectedRoomIds.size}개 삭제`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(renameTarget)}
        onOpenChange={(open) => !open && !isRenaming && setRenameTarget(null)}
      >
        <DialogContent data-chat-widget-portal="true" className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>대화방 이름 변경</DialogTitle>
            <DialogDescription>목록에서 알아보기 쉬운 이름을 입력하세요.</DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            maxLength={120}
            autoFocus
          />
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">취소</Button>
            </DialogClose>
            <Button
              type="button"
              disabled={!renameValue.trim() || isRenaming}
              onClick={async () => {
                setIsRenaming(true)
                try {
                  const result = await onRenameRoom?.(renameTarget?.id, renameValue)
                  if (result?.ok !== false) setRenameTarget(null)
                } finally {
                  setIsRenaming(false)
                }
              }}
            >
              {isRenaming ? <Loader2 className="size-4 animate-spin" /> : null}
              {isRenaming ? "저장 중" : "저장"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
