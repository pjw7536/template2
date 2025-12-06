import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useEventLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "event", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/event", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
