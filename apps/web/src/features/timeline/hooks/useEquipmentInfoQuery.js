import { useQuery } from "@tanstack/react-query"

import { timelineQueryKeys } from "../api/query-keys"
import { timelineApi } from "../api/timelineApi"

export function useEquipmentInfoQuery(eqpId, options = {}) {
  const enabled = Boolean(eqpId) && (options.enabled ?? true)

  return useQuery({
    queryKey: timelineQueryKeys.equipmentInfo(eqpId ?? null),
    queryFn: () => timelineApi.fetchEquipmentInfoByEqpId(eqpId),
    enabled,
  })
}
