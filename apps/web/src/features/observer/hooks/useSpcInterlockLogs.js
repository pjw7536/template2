import { useObserverLogQuery } from "./useObserverLogQuery";

export const useSpcInterlockLogs = (eqpId, logQueryOptions, options) =>
  useObserverLogQuery("spc-interlock", eqpId, logQueryOptions, options);
