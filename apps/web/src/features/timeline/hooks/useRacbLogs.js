import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useRacbLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "racb", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/racb", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
