import { DEFAULT_TYPE_FILTERS } from "./constants";
import { getLogKey, OBSERVER_LOG_CONFIG } from "./logPagination";
import { getObserverEquipmentPath } from "./observerLocation";

const EVIDENCE_ID_PARAM = "evidenceId";
const LOG_TYPE_PARAM = "analysisLogType";
const TIP_GROUP_PARAM = "analysisTipGroup";

function normalizeString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeList(value) {
  return Array.isArray(value)
    ? Array.from(new Set(value.map(normalizeString).filter(Boolean)))
    : [];
}

function normalizeDate(value) {
  return normalizeString(value).slice(0, 10);
}

export function buildObserverEvidenceHref(scope, evidenceId) {
  const eqpId = normalizeString(scope?.eqpId);
  const normalizedEvidenceId = normalizeString(evidenceId);
  if (!eqpId || !normalizedEvidenceId) return "";

  const params = new URLSearchParams();
  const from = normalizeDate(scope?.from);
  const to = normalizeDate(scope?.to);
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  params.set(EVIDENCE_ID_PARAM, normalizedEvidenceId);
  normalizeList(scope?.logTypes).forEach((logType) =>
    params.append(LOG_TYPE_PARAM, logType)
  );
  normalizeList(scope?.tipGroups).forEach((tipGroup) =>
    params.append(TIP_GROUP_PARAM, tipGroup)
  );
  return `${getObserverEquipmentPath(eqpId)}?${params.toString()}`;
}

export function getObserverEvidenceNavigation(searchParams) {
  const evidenceId = normalizeString(searchParams?.get(EVIDENCE_ID_PARAM));
  if (!evidenceId) return null;
  const evidenceLogType = evidenceId.split(":", 1)[0].toUpperCase();
  return {
    evidenceId,
    logKey: getLogKey(evidenceLogType),
    from: normalizeDate(searchParams.get("from")),
    to: normalizeDate(searchParams.get("to")),
    logTypes: normalizeList(searchParams.getAll(LOG_TYPE_PARAM)),
    tipGroups: normalizeList(searchParams.getAll(TIP_GROUP_PARAM)),
  };
}

export function buildEvidenceTypeFilters(logTypes) {
  const normalizedLogTypes = new Set(normalizeList(logTypes));
  if (!normalizedLogTypes.size) return { ...DEFAULT_TYPE_FILTERS };
  return Object.fromEntries(
    OBSERVER_LOG_CONFIG.map(({ filterType, logKey }) => [
      filterType,
      normalizedLogTypes.has(logKey),
    ])
  );
}

export function matchesObserverEvidence(log, evidenceId) {
  const normalizedEvidenceId = normalizeString(evidenceId);
  if (!log || !normalizedEvidenceId) return false;
  const logType = normalizeString(log.logType).toUpperCase();
  const candidates = [log.id, log.sourceId]
    .map((value) => normalizeString(String(value ?? "")))
    .filter(Boolean);
  return candidates.some(
    (candidate) =>
      candidate === normalizedEvidenceId ||
      `${logType}:${candidate}` === normalizedEvidenceId
  );
}

export function getObserverScopeSignature(scope) {
  if (!scope || typeof scope !== "object") return "";
  return JSON.stringify({
    eqpId: normalizeString(scope.eqpId).toUpperCase(),
    from: normalizeDate(scope.from),
    to: normalizeDate(scope.to),
    logTypes: normalizeList(scope.logTypes).sort(),
    tipGroups: normalizeList(scope.tipGroups).sort(),
  });
}
