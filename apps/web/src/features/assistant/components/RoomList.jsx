import { Button } from "@/components/ui/button"

export function RoomList({ rooms = [], activeRoomId, onSelectRoom }) {
  const hasRooms = Array.isArray(rooms) && rooms.length > 0

  return (
    <div className="space-y-1 overflow-y-auto px-2 pb-3">
      {hasRooms &&
        rooms.map((room) => (
          <Button
            key={room.id}
            variant={room.id === activeRoomId ? "secondary" : "ghost"}
            size="sm"
            className="w-full justify-between truncate"
            onClick={() => onSelectRoom?.(room.id)}
          >
            <span className="truncate text-left text-sm">{room.name}</span>
            {room.id === activeRoomId ? (
              <span className="text-[10px] text-primary">현재</span>
            ) : (
              <span className="text-[10px] text-muted-foreground" />
            )}
          </Button>
        ))}

      {!hasRooms && (
        <div className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          아직 대화방이 없습니다.
        </div>
      )}
    </div>
  )
}
