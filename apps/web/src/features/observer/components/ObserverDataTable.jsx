import React, { useEffect, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useObserverSelectionStore } from "../store/useObserverSelectionStore";
import ObserverTableHeader from "./table/ObserverTableHeader";
import ObserverTableFilters from "./table/ObserverTableFilters";
import ObserverTableRow from "./table/ObserverTableRow";

export default function ObserverDataTable({
  data,
  typeFilters,
  handleFilter,
  getLogTypeBadgeClass,
}) {
  const { selectedRow, source, setSelectedRow } = useObserverSelectionStore();
  const scrollContainerRef = useRef(null);
  const rowIndexById = useMemo(
    () =>
      new Map(
        data.map((row, index) => [String(row.id), index])
      ),
    [data]
  );
  const rowVirtualizer = useVirtualizer({
    count: data.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 40,
    getItemKey: (index) => data[index]?.id ?? index,
    overscan: 10,
  });

  useEffect(() => {
    if (source !== "observer" || !selectedRow) return;
    const selectedIndex = rowIndexById.get(String(selectedRow));
    if (selectedIndex === undefined) return;

    rowVirtualizer.scrollToIndex(selectedIndex, {
      align: "center",
      behavior: "smooth",
    });
  }, [rowIndexById, rowVirtualizer, selectedRow, source]);

  const handleSelect = (rowId) => setSelectedRow(rowId, "table");

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex justify-between items-center pt-1 bg-card text-foreground rounded-t-lg border-b border-border">
        <h3 className="text-md font-semibold mb-5">📜 Data Log</h3>
        <ObserverTableFilters
          typeFilters={typeFilters}
          handleFilter={handleFilter}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {data.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            표시할 데이터가 없습니다.
          </div>
        ) : (
          <div className="grid h-full min-h-0 grid-rows-[auto_1fr] overflow-hidden rounded-b-lg border border-border bg-card">
            <ObserverTableHeader />
            <div
              ref={scrollContainerRef}
              className="min-h-0 overflow-auto"
              role="listbox"
              aria-label="Observer 로그 목록"
            >
              <div
                className="relative w-full"
                style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const row = data[virtualRow.index];

                  return (
                    <div
                      key={virtualRow.key}
                      ref={rowVirtualizer.measureElement}
                      data-index={virtualRow.index}
                      className="absolute left-0 top-0 w-full"
                      style={{
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      <ObserverTableRow
                        row={row}
                        isSelected={String(row.id) === String(selectedRow)}
                        onSelect={handleSelect}
                        getLogTypeBadgeClass={getLogTypeBadgeClass}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
