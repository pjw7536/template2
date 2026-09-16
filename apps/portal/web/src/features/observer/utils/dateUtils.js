export const OBSERVER_TIME_ZONE = "Asia/Seoul";

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const SEOUL_UTC_OFFSET_IN_MS = 9 * 60 * 60 * 1000;
const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: OBSERVER_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

function getSeoulDateTimeParts(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  return Object.fromEntries(
    DATE_TIME_FORMATTER.formatToParts(date)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value: partValue }) => [type, partValue])
  );
}

/** Observer 시각을 'YY/MM/DD HH:mm' 형식의 한국 시간으로 표시합니다. */
export function formatDateTime(value) {
  const parts = getSeoulDateTimeParts(value);
  if (!parts) return value;

  return `${parts.year.slice(-2)}/${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
}

/** Observer 상세 시각을 초 단위 한국 시간으로 표시합니다. */
export function formatDetailDateTime(value) {
  const parts = getSeoulDateTimeParts(value);
  if (!parts) return value;

  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

/** 주어진 instant가 속한 한국 날짜를 UTC 자정 Date로 반환합니다. */
export function getSeoulCalendarDate(value = new Date()) {
  const parts = getSeoulDateTimeParts(value);
  if (!parts) return null;

  return new Date(
    Date.UTC(
      Number(parts.year),
      Number(parts.month) - 1,
      Number(parts.day)
    )
  );
}

/** 주어진 instant가 속한 한국 날짜의 시작 instant를 반환합니다. */
export function getStartOfSeoulDay(value = new Date()) {
  const calendarDate = getSeoulCalendarDate(value);
  if (!calendarDate) return null;
  return new Date(calendarDate.getTime() - SEOUL_UTC_OFFSET_IN_MS);
}

/** 주어진 instant가 속한 한국 날짜의 마지막 instant를 반환합니다. */
export function getEndOfSeoulDay(value = new Date()) {
  const start = getStartOfSeoulDay(value);
  if (!start) return null;
  return new Date(start.getTime() + DAY_IN_MS - 1);
}

