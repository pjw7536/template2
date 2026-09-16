import { DATA_TYPES } from "./constants";

export const OBSERVER_LOG_PAGE_SIZE = 250;
export const OBSERVER_RESIDENT_LOG_LIMIT = 5000;

export const OBSERVER_LOG_CONFIG = [
  { filterType: DATA_TYPES.EQP, logKey: "eqp", label: "EQP" },
  { filterType: DATA_TYPES.TIP, logKey: "tip", label: "TIP" },
  {
    filterType: DATA_TYPES.SPC_ITL,
    logKey: "spc-interlock",
    label: "SPC Interlock",
  },
  {
    filterType: DATA_TYPES.FDC_ITL,
    logKey: "fdc-interlock",
    label: "FDC Interlock",
  },
  { filterType: DATA_TYPES.CTTTM, logKey: "ctttm", label: "CTTTM" },
  { filterType: DATA_TYPES.RACB, logKey: "racb", label: "RACB" },
  { filterType: DATA_TYPES.ESOP, logKey: "esop", label: "ESOP" },
];

const LOG_TYPE_TO_KEY = new Map([
  ["EQP", "eqp"],
  ["TIP", "tip"],
  ["SPC_ITL", "spc-interlock"],
  ["FDC_ITL", "fdc-interlock"],
  ["CTTTM", "ctttm"],
  ["RACB", "racb"],
  ["ESOP", "esop"],
]);

export function getEnabledLogKeys(typeFilters) {
  return OBSERVER_LOG_CONFIG.filter(
    ({ filterType }) => typeFilters?.[filterType]
  ).map(({ logKey }) => logKey);
}

export function getLogKey(logType) {
  return LOG_TYPE_TO_KEY.get(logType) || "";
}

export function mergeUniqueLogItems(pages, limit) {
  const seen = new Set();
  const merged = [];

  for (const page of pages) {
    for (const item of page || []) {
      const key = `${item.logType}:${item.id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      merged.push(item);
      if (merged.length >= limit) return merged;
    }
  }

  return merged;
}
