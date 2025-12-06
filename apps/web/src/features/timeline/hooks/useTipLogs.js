import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useTipLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "tip", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/tip", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
