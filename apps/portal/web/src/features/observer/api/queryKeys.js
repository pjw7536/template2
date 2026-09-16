const ROOT_KEY = ["observer"]

export const observerQueryKeys = {
  all: ROOT_KEY,
  equipmentInfo: (eqpId) => [...ROOT_KEY, "equipment-info", eqpId ?? null],
  logs: (logKey, eqpId, options) => [
    ...ROOT_KEY,
    "logs",
    logKey,
    eqpId ?? null,
    options ?? {},
  ],
  logBatch: (eqpId, types, options) => [
    ...ROOT_KEY,
    "log-batch",
    eqpId ?? null,
    types,
    options ?? {},
  ],
  logPage: (logKey, eqpId, options, cursor) => [
    ...ROOT_KEY,
    "log-page",
    logKey,
    eqpId ?? null,
    options ?? {},
    cursor ?? null,
  ],
  logDetail: (logKey, eqpId, detailId) => [
    ...ROOT_KEY,
    "log-detail",
    logKey,
    eqpId ?? null,
    detailId ?? null,
  ],
  evidenceLog: (logKey, eqpId, evidenceId, range) => [
    ...ROOT_KEY,
    "evidence-log",
    logKey,
    eqpId ?? null,
    evidenceId ?? null,
    range ?? {},
  ],
}
