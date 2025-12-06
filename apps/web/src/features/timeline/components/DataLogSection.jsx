// src/features/timeline/components/DataLogSection.jsx
import React from "react";
import TimelineDataTable from "./TimelineDataTable";
import { LoadingSpinner } from "./Loaders";
import { getLogTypeBadgeClass } from "../utils/logTypeStyles";

export default function DataLogSection({
  eqpId,
  logsLoading,
  tableData,
  typeFilters,
  handleFilter,
}) {
  return (
    <section className="border border-border bg-card shadow-sm rounded-xl p-3 flex-[2] min-h-0 flex flex-col overflow-hidden">
      {!eqpId && !logsLoading ? (
        <p className="text-center text-sm text-muted-foreground py-4">
          EQP를 선택하세요.
        </p>
      ) : logsLoading ? (
        <div className="flex items-center justify-center h-full">
          <LoadingSpinner />
        </div>
      ) : (
        <TimelineDataTable
          data={tableData}
          typeFilters={typeFilters}
          handleFilter={handleFilter}
          getLogTypeBadgeClass={getLogTypeBadgeClass}
        />
      )}
    </section>
  );
}
