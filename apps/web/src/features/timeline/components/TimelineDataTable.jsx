import React, { useEffect, useRef } from "react";
import { LinkIcon } from "@heroicons/react/24/outline";
import { useTimelineSelectionStore } from "../store/useTimelineSelectionStore";

const columnWidths = {
  time: 112,
  logType: 80,
  changeType: 160,
  operator: 70,
  duration: 70,
  url: 70,
};

function TableHeader() {
  return (
    <div className="sticky top-0 z-10 bg-muted text-muted-foreground">
      <div className="flex text-xs font-semibold">
        <div
          style={{ width: `${columnWidths.time}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Time
        </div>
        <div
          style={{ width: `${columnWidths.logType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          LogType
        </div>
        <div
          style={{ width: `${columnWidths.changeType}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          ChangeType
        </div>
        <div
          style={{ width: `${columnWidths.operator}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Operator
        </div>
        <div
          style={{ width: `${columnWidths.duration}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          Duration
        </div>
        <div
          style={{ width: `${columnWidths.url}px` }}
          className="px-2 py-2 text-center flex-shrink-0"
        >
          URL
        </div>
      </div>
    </div>
  );
}

function FilterCheckboxes({ typeFilters, handleFilter }) {
  return (
    <div className="flex gap-3 flex-wrap mr-3">
      {Object.entries(typeFilters).map(([type, checked]) => (
        <label key={type} className="flex items-center gap-1 text-xs font-bold">
          <input
          type="checkbox"
          name={type}
          checked={checked}
          onChange={handleFilter}
          className="rounded border border-border"
        />
        {type.replace("_LOG", "")}
      </label>
    ))}
  </div>
  );
}

function DataRow({ row, isSelected, onSelect }) {
  const baseClasses =
    "flex items-center cursor-pointer border-b border-border hover:bg-muted";
  const selectionClasses = isSelected
    ? "bg-yellow-200 dark:bg-yellow-800 dark:ring-yellow-700 transition-all duration-200"
    : "bg-card transition-colors duration-150";

  const handleRowClick = () => {
    onSelect(isSelected ? null : row.id);
  };

  const handleUrlClick = (e) => {
    e.stopPropagation();
    if (row.url) {
      window.open(row.url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div
      data-row-id={row.id}
      onClick={handleRowClick}
      className={`${baseClasses} ${selectionClasses}`}
    >
      <div
        style={{ width: `${columnWidths.time}px` }}
        className="px-2 py-2 text-xs text-center text-gray-800 dark:text-gray-200 flex-shrink-0"
      >
        {row.displayTimestamp}
      </div>
      <div
        style={{ width: `${columnWidths.logType}px` }}
        className="px-2 py-2 text-xs text-center text-gray-800 dark:text-gray-200 flex-shrink-0"
      >
        <span
          className={`
           inline-block px-2 py-1 text-xs font-medium rounded
           ${
             row.logType === "EQP"
               ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
               : ""
           }
           ${
             row.logType === "TIP"
               ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
               : ""
           }
           ${
             row.logType === "RACB"
               ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
               : ""
           }
           ${
             row.logType === "CTTTM"
               ? "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
               : ""
           }
           ${
             row.logType === "JIRA"
               ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
               : ""
           }
         `}
        >
          {row.logType}
        </span>
      </div>
      <div
        style={{ width: `${columnWidths.changeType}px` }}
        className="px-2 py-2 text-xs text-center text-gray-800 dark:text-gray-200 flex-shrink-0"
      >
        {row.info1}
      </div>
      <div
        style={{ width: `${columnWidths.operator}px` }}
        className="px-2 py-2 text-xs text-center text-gray-800 dark:text-gray-200 flex-shrink-0"
      >
        {row.info2}
      </div>
      <div
        style={{ width: `${columnWidths.duration}px` }}
        className="px-2 py-2 text-xs text-center text-gray-800 dark:text-gray-200 flex-shrink-0"
      >
        {row.duration}
      </div>
      <div
        style={{ width: `${columnWidths.url}px` }}
        className="px-2 py-2 text-xs text-center flex-shrink-0"
      >
        {row.url ? (
          <button
            onClick={handleUrlClick}
            className="inline-flex items-center justify-center w-8 h-8 rounded hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
            title="Open URL"
          >
            <LinkIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          </button>
        ) : (
          <span className="text-gray-400 dark:text-gray-600">-</span>
        )}
      </div>
    </div>
  );
}

export default function TimelineDataTable({ data, typeFilters, handleFilter }) {
  const { selectedRow, source, setSelectedRow } = useTimelineSelectionStore();
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    if (source !== "timeline" || !selectedRow) return;
    const container = scrollContainerRef.current;
    if (!container) return;

    const target = container.querySelector(
      `[data-row-id="${String(selectedRow)}"]`
    );
    if (!target) return;

    const containerRect = container.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offsetTop = targetRect.top - containerRect.top;
    const targetCenter = offsetTop + targetRect.height / 2;
    const scrollTarget =
      container.scrollTop + targetCenter - container.clientHeight / 2;

    container.scrollTo({
      top: Math.max(scrollTarget, 0),
      behavior: "smooth",
    });
  }, [selectedRow, source]);

  const handleSelect = (rowId) => setSelectedRow(rowId, "table");

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex justify-between items-center pt-1 bg-card text-foreground rounded-t-lg border-b border-border">
        <h3 className="text-md font-semibold mb-5">📜 Data Log</h3>
        <FilterCheckboxes typeFilters={typeFilters} handleFilter={handleFilter} />
      </div>

      <div className="flex-1 overflow-hidden">
        {data.length === 0 ? (
          <div className="text-center text-sm text-gray-500 dark:text-gray-400 p-4">
            표시할 데이터가 없습니다.
          </div>
        ) : (
          <div className="h-full bg-card rounded-b-lg overflow-hidden border border-border">
            <TableHeader />
            <div
              ref={scrollContainerRef}
              className="h-full overflow-auto"
              role="list"
            >
              {data.map((row) => (
                <DataRow
                  key={row.id}
                  row={row}
                  isSelected={String(row.id) === String(selectedRow)}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
