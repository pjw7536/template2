function getMessageTimestamp(message) {
  if (!message?.id) return 0
  const [, tsPart] = String(message.id).split("-")
  const ts = Number(tsPart)
  return Number.isFinite(ts) ? ts : 0
}

function getLastQuestionTimestamp(room, messagesByRoom = {}) {
  const updatedAt = Date.parse(room?.updatedAt || "")
  if (Number.isFinite(updatedAt)) return updatedAt
  const roomId = room?.id
  const roomMessages = messagesByRoom[roomId] || []
  const lastUser = [...roomMessages].reverse().find((message) => message.role === "user")
  if (lastUser) return getMessageTimestamp(lastUser)

  const lastMessage = roomMessages[roomMessages.length - 1]
  return getMessageTimestamp(lastMessage)
}

export function sortRoomsByRecentQuestion(rooms = [], messagesByRoom = {}) {
  return [...rooms].sort((a, b) => {
    if (a?.pinned !== b?.pinned) return a?.pinned ? -1 : 1
    return (
      getLastQuestionTimestamp(b, messagesByRoom) -
      getLastQuestionTimestamp(a, messagesByRoom)
    )
  })
}
