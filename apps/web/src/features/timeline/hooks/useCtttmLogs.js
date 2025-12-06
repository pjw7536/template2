import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useCtttmLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "ctttm", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/ctttm", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
