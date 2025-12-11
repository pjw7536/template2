const ROOT_KEY = ["timeline"]

export const timelineQueryKeys = {
  all: ROOT_KEY,
  equipmentInfo: (eqpId) => [...ROOT_KEY, "equipment-info", eqpId ?? null],
}
