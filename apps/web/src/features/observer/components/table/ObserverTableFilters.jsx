import React from "react";
import { DATA_TYPE_LABELS } from "../../utils/constants";

export default function ObserverTableFilters({ typeFilters, handleFilter }) {
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
          {DATA_TYPE_LABELS[type] || type.replace("_LOG", "")}
        </label>
      ))}
    </div>
  );
}
