export const DATA_TYPES = {
  EQP: "EQP",
  TIP: "TIP",
  SPC_ITL: "SPC_ITL",
  FDC_ITL: "FDC_ITL",
  RACB: "RACB",
  CTTTM: "CTTTM",
  ESOP: "ESOP",
};

export const DEFAULT_TYPE_FILTERS = {
  [DATA_TYPES.EQP]: true,
  [DATA_TYPES.TIP]: true,
  [DATA_TYPES.SPC_ITL]: true,
  [DATA_TYPES.FDC_ITL]: true,
  [DATA_TYPES.RACB]: true,
  [DATA_TYPES.CTTTM]: true,
  [DATA_TYPES.ESOP]: true,
};

export const DATA_TYPE_LABELS = {
  [DATA_TYPES.EQP]: "EQP",
  [DATA_TYPES.TIP]: "TIP",
  [DATA_TYPES.SPC_ITL]: "SPC Interlock",
  [DATA_TYPES.FDC_ITL]: "FDC Interlock",
  [DATA_TYPES.RACB]: "RACB",
  [DATA_TYPES.CTTTM]: "CTTTM",
  [DATA_TYPES.ESOP]: "ESOP",
};

export const DEFAULT_LOG_QUERY_OPTIONS = {};
export const MIN_LOG_RANGE_DAYS = 1;
export const DEFAULT_LOG_RANGE_DAYS = 7;
export const MAX_LOG_RANGE_DAYS = 90;
export const LOG_RANGE_SLIDER_STEP = 1;
