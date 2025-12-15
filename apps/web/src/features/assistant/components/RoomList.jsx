import { Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"

export function RoomList({ rooms = [], activeRoomId, onSelectRoom, onDeleteRoom }) {
  const hasRooms = Array.isArray(rooms) && rooms.length > 0

  return (
    <div className="space-y-1">
      {hasRooms &&
        rooms.map((room) => (
          <div key={room.id} className="flex items-center gap-2">
            <Button
              variant={room.id === activeRoomId ? "secondary" : "ghost"}
              size="sm"
              className="flex-1 justify-between truncate"
              onClick={() => onSelectRoom?.(room.id)}
            >
              <span className="truncate text-left text-sm">{room.name}</span>
              {room.id === activeRoomId ? (
                <span className="text-[10px] text-primary">현재</span>
              ) : (
                <span className="text-[10px] text-muted-foreground" />
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 text-muted-foreground"
              onClick={(event) => {
                event.stopPropagation()
                onDeleteRoom?.(room.id)
              }}
              aria-label={`${room.name} 삭제`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}

      {!hasRooms && (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          아직 대화방이 없습니다.
        </div>
      )}
    </div>
  )
}
