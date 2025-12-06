import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useEqpLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "eqp", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/eqp", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
