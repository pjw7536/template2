import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useJiraLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "jira", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/jira", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
