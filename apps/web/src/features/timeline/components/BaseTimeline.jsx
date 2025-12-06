// src/features/timeline/components/BaseTimeline.jsx
import React, { useRef, useMemo } from "react";
import { useVisTimeline } from "../hooks/useVisTimeline";

/**
 * 재사용 가능한 기본 Timeline 컴포넌트
 * @param {Object} props
 * @param {Array} props.groups - 타임라인 그룹 정의
 * @param {Array} props.items - 타임라인 아이템
 * @param {Object} props.options - vis-timeline 옵션
 * @param {string} props.title - 타임라인 제목
 * @param {ReactNode} props.headerExtra - 헤더 추가 요소
 * @param {boolean} props.showTimeAxis - x축 표시 여부
 */
export default function BaseTimeline({
  groups,
  items,
  options = {},
  title,
  headerExtra,
  className = "",
  style = {},
  showTimeAxis = true,
  height,
  minHeight,
  maxHeight,
}) {
  const containerRef = useRef(null);

  const mergedOptions = useMemo(
    () => ({
      margin: { item: 0, axis: 0 },
      groupOrder: "order",
      selectable: true,
      verticalScroll:
        options.verticalScroll !== undefined ? options.verticalScroll : true,
      tooltip: {
        followMouse: true,
        overflowMethod: "flip",
      },
      showMajorLabels: showTimeAxis,
      showMinorLabels: showTimeAxis,
      align: "center",
      orientation: {
        item: "top",
      },
      ...(height !== undefined && { height }),
      ...(minHeight !== undefined && { minHeight }),
      ...(maxHeight !== undefined && { maxHeight }),
      ...options,
    }),
    [options, showTimeAxis, height, minHeight, maxHeight]
  );

  useVisTimeline({
    containerRef,
    groups,
    items,
    options: mergedOptions,
  });

  // 동적 스타일 계산
  const containerStyle = {
    ...style,
    ...(mergedOptions.height ? { height: `${mergedOptions.height}px` } : {}),
  };

  return (
    <div
      className={`timeline-container relative ${className} ${
        !showTimeAxis ? "no-time-axis" : ""
      }`}
    >
      {(title || headerExtra) && (
        <div className="flex items-center justify-between">
          {title && (
            <h3 className="text-sm font-semibold text-slate-600 dark:text-slate-300">
              {title}
            </h3>
          )}
          {headerExtra}
        </div>
      )}

      <div ref={containerRef} className="timeline" style={containerStyle} />
    </div>
  );
}
