import React, { useCallback, useRef } from "react";
import EqpDetail from "./EqpDetail";
import TipDetail from "./TipDetail";
import RacbDetail from "./RacbDetail";
import CtttmDetail from "./CtttmDetail";
import EsopDetail from "./EsopDetail";
import InterlockDetail from "./InterlockDetail";

function findScrollableParent(element) {
  let current = element;

  while (current) {
    const { overflowY } = window.getComputedStyle(current);
    const canScroll = /(auto|scroll|overlay)/.test(overflowY) && current.scrollHeight > current.clientHeight;
    if (canScroll) {
      return current;
    }
    current = current.parentElement;
  }

  return element;
}

/**
 * 선택된 로그 상세정보를 보여주는 컴포넌트
 * 로그 타입에 따라 적절한 상세 컴포넌트를 렌더링합니다
 * @param {Object} log - 상세를 보여줄 로그 객체
 */
export default function LogDetailSection({
  log,
  isLoading = false,
  error = null,
  onRetry,
  className = "",
  overflowClassName = "overflow-auto",
  textSizeClass = "text-xs",
  summaryStreamingScrollClassName,
}) {
  const detailRef = useRef(null);
  const handleStreamingProgress = useCallback(() => {
    const detailElement = detailRef.current;
    if (!detailElement) return;

    window.requestAnimationFrame(() => {
      const scrollContainer = findScrollableParent(detailElement);
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    });
  }, []);

  if (!log) {
    return (
      <div className="text-sm text-muted-foreground text-center py-17">
        테이블이나 Observer에서 로그를 선택하면 상세정보가 표시됩니다.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        선택한 로그의 상세정보를 불러오고 있습니다.
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-destructive">
        <p>상세정보를 불러오지 못했습니다.</p>
        {onRetry ? (
          <button
            type="button"
            onClick={() => onRetry()}
            className="rounded-md border border-destructive/30 px-3 py-1.5 font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            다시 시도
          </button>
        ) : null}
      </div>
    );
  }

  // 로그 타입에 따라 적절한 컴포넌트 렌더링
  const renderDetailComponent = () => {
    switch (log.logType) {
      case "EQP":
        return <EqpDetail log={log} />;
      case "TIP":
        return <TipDetail log={log} />;
      case "SPC_ITL":
      case "FDC_ITL":
        return <InterlockDetail log={log} />;
      case "RACB":
        return <RacbDetail log={log} />;
      case "CTTTM":
        return (
          <CtttmDetail
            log={log}
            summaryStreamingScrollClassName={summaryStreamingScrollClassName}
            onStreamingProgress={handleStreamingProgress}
          />
        );
      case "ESOP":
        return <EsopDetail log={log} />;
      default:
        return (
          <div className="col-span-4 text-muted-foreground py-2">
            알 수 없는 로그 타입입니다.
          </div>
        );
    }
  };

  return (
    <div
      ref={detailRef}
      className={`grid grid-cols-[max-content_minmax(0,1fr)_max-content_minmax(0,1fr)] gap-x-4 gap-y-2 ${textSizeClass}
       rounded-lg p-2
      text-foreground ${overflowClassName} ${className}`}
    >
      {renderDetailComponent()}
    </div>
  );
}
