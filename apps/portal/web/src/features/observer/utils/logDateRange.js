import {
  DEFAULT_LOG_RANGE_DAYS,
  MAX_LOG_RANGE_DAYS,
  MIN_LOG_RANGE_DAYS,
} from "./constants";
import { getSeoulCalendarDate } from "./dateUtils";

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const DATE_PARAM_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function toValidNumber(value, fallback = DEFAULT_LOG_RANGE_DAYS) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
}

export function clampLogRangeDays(value) {
  const numberValue = Math.round(toValidNumber(value));
  return Math.min(Math.max(numberValue, MIN_LOG_RANGE_DAYS), MAX_LOG_RANGE_DAYS);
}

export function getDefaultLogRange() {
  return {
    startDaysAgo: DEFAULT_LOG_RANGE_DAYS,
    endDaysAgo: MIN_LOG_RANGE_DAYS,
  };
}

export function normalizeLogRange(value) {
  if (typeof value === "number") {
    return {
      startDaysAgo: clampLogRangeDays(value),
      endDaysAgo: MIN_LOG_RANGE_DAYS,
    };
  }

  const fallback = getDefaultLogRange();
  const startCandidate = value?.startDaysAgo ?? fallback.startDaysAgo;
  const endCandidate = value?.endDaysAgo ?? fallback.endDaysAgo;
  const startDaysAgo = clampLogRangeDays(startCandidate);
  const endDaysAgo = clampLogRangeDays(endCandidate);

  return {
    startDaysAgo: Math.max(startDaysAgo, endDaysAgo),
    endDaysAgo: Math.min(startDaysAgo, endDaysAgo),
  };
}

function formatDateParam(date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateParam(value) {
  if (!DATE_PARAM_PATTERN.test(value || "")) return null;

  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }

  return date;
}

function formatDateLabel(date) {
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${month}/${day}`;
}

function getDateFromDaysAgo(daysAgo) {
  const date = getSeoulCalendarDate();
  date.setUTCDate(date.getUTCDate() - clampLogRangeDays(daysAgo) + 1);
  return date;
}

function getUtcDayNumber(date) {
  return Math.floor(date.getTime() / DAY_IN_MS);
}

function getDaysAgoFromDate(date) {
  const today = getSeoulCalendarDate();
  const diffDays = getUtcDayNumber(today) - getUtcDayNumber(date);
  return clampLogRangeDays(diffDays + 1);
}

export function getLogDateRange(rangeValue) {
  const range = normalizeLogRange(rangeValue);
  const from = getDateFromDaysAgo(range.startDaysAgo);
  const to = getDateFromDaysAgo(range.endDaysAgo);

  return { from, to, ...range };
}

export function getLogRangeSpanDays(rangeValue) {
  const range = normalizeLogRange(rangeValue);
  return range.startDaysAgo - range.endDaysAgo + 1;
}

export function getRecentLogDateRange(rangeDays) {
  const days = clampLogRangeDays(rangeDays);
  const to = getSeoulCalendarDate();
  const from = new Date(to);
  from.setUTCDate(to.getUTCDate() - days + 1);

  return { from, to, days };
}

export function buildLogDateRangeOptions(rangeValue) {
  const { from, to } = getLogDateRange(rangeValue);
  return {
    from: formatDateParam(from),
    to: formatDateParam(to),
  };
}

export function getLogRangeFromSearchParams(searchParams) {
  const dateParam = searchParams.get("date");
  const fromParam =
    searchParams.get("from") || searchParams.get("date_from") || dateParam;
  const toParam =
    searchParams.get("to") || searchParams.get("date_to") || dateParam;
  const fromDate = parseDateParam(fromParam);
  const toDate = parseDateParam(toParam);

  if (!fromDate || !toDate) return null;

  const fromDaysAgo = getDaysAgoFromDate(fromDate);
  const toDaysAgo = getDaysAgoFromDate(toDate);

  return normalizeLogRange({
    startDaysAgo: Math.max(fromDaysAgo, toDaysAgo),
    endDaysAgo: Math.min(fromDaysAgo, toDaysAgo),
  });
}

export function formatLogRangeLabel(rangeValue) {
  const spanDays = getLogRangeSpanDays(rangeValue);
  return `${spanDays} days`;
}

export function formatLogRangeWindow(rangeValue) {
  const { from, to } = getLogDateRange(rangeValue);
  return `${formatDateLabel(from)} ~ ${formatDateLabel(to)}`;
}
