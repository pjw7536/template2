// src/features/timeline/utils/timelineUtils.js
// 미사용 함수 제거하고 필요한 것만 남김
import { groupConfig } from "./timelineMeta";

/** ➜ vis-timeline 아이템 변환 */
export const processData = (logType, data, makeRangeContinuous = false) => {
  const cfg = groupConfig[logType];
  if (!cfg) return [];

  // 데이터를 eventTime 순으로 정렬
  const sortedData = data
    .filter((l) => l && l.eventTime)
    .sort((a, b) => new Date(a.eventTime) - new Date(b.eventTime));

  return sortedData.map((l, index) => {
    const start = new Date(l.eventTime);
    let end = start; // 기본값은 point 형태
    let isRange = false;

    // makeRangeContinuous가 true인 경우 range로 만들기
    if (makeRangeContinuous) {
      if (index < sortedData.length - 1) {
        // 다음 로그의 eventTime을 현재 로그의 endTime으로 설정
        end = new Date(sortedData[index + 1].eventTime);
      } else {
        // 마지막 로그인 경우
        const now = new Date();
        const todayMidnight = new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate(),
          0,
          0,
          0,
          0
        );

        if (start < todayMidnight) {
          // eventTime이 오늘 00:00:00보다 이전이면, 오늘 00:00:00으로 설정
          end = todayMidnight;
        } else {
          // eventTime이 오늘 00:00:00보다 이후면, eventTime + 1시간으로 설정
          end = new Date(start.getTime() + 60 * 60 * 1000); // 1시간 추가
        }
      }
      isRange = true;
    }

    const colorCls = cfg.stateColors[l.eventType] || "bg-gray-300";

    // 폰트 크기를 logType에 따라 다르게 설정
    const fontSize =
      {
        EQP: "12px",
        TIP: "11px",
        CTTTM: "10px",
        RACB: "10px",
        JIRA: "10px",
      }[logType] || "11px";

    return {
      id: l.id,
      group: logType,
      content: `<span style="font-size: ${fontSize}; font-weight: 500;">${
        l.eventType || ""
      }</span>`,
      start,
      end,
      type: isRange ? "range" : "point",
      className: colorCls,
      title: [
        l.comment,
        l.operator ? `👤 ${l.operator}` : null,
        l.url ? `🔗 ${l.url}` : null,
      ]
        .filter(Boolean)
        .join("\n"),
    };
  });
};

/** 전체 로그 범위 계산 */
export const calcRange = (logs) => {
  if (!logs || logs.length === 0) {
    // 로그가 없을 때 기본값
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  // eventTime이 있는 로그만 필터링
  const validLogs = logs.filter((log) => log && log.eventTime);

  if (validLogs.length === 0) {
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  // 모든 시간을 추출 (eventTime과 endTime 모두 고려)
  const allTimes = [];

  validLogs.forEach((log) => {
    const eventTime = new Date(log.eventTime).getTime();
    if (!isNaN(eventTime)) {
      allTimes.push(eventTime);
    }

    // endTime도 있다면 포함
    if (log.endTime) {
      const endTime = new Date(log.endTime).getTime();
      if (!isNaN(endTime)) {
        allTimes.push(endTime);
      }
    }
  });

  if (allTimes.length === 0) {
    const now = new Date();
    return {
      min: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      max: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1),
    };
  }

  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);

  return {
    min: new Date(minTime),
    max: new Date(maxTime),
  };
};

const getEndOfToday = () => {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
};

/** 버퍼 추가 (줌 아웃 시 오늘까지는 항상 포함) */
export const addBuffer = (min, max) => {
  const todayEnd = getEndOfToday().getTime();
  const effectiveMax = Math.max(max, todayEnd);
  const range = effectiveMax - min;
  const bufferRatio = 0.1; // 전체 범위의 10%를 버퍼로
  const buffer = Math.max(range * bufferRatio, 24 * 60 * 60 * 1000); // 최소 1일

  return {
    min: new Date(min - buffer),
    max: new Date(effectiveMax + buffer),
  };
};
