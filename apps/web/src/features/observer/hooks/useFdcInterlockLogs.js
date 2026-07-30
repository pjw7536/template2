import { useObserverLogQuery } from "./useObserverLogQuery";

export const useFdcInterlockLogs = (eqpId, logQueryOptions, options) =>
  useObserverLogQuery("fdc-interlock", eqpId, logQueryOptions, options);
