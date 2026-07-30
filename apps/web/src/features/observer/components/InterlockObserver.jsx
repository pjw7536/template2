import React from "react";
import BaseObserver from "./BaseObserver";
import ObserverLegend from "./ObserverLegend";
import ObserverEmptyState from "./ObserverEmptyState";
import { buildFixedHeightOptions } from "../utils/observerUtils";
import { processData } from "../utils/visObserverItems";
import { makeGroupLabel } from "../utils/groupLabel";
import { observerLegends } from "../utils/observerLegends";

export default function InterlockObserver({
  range,
  logType,
  title,
  showLegend,
  showTimeAxis = false,
  logs = [],
}) {
  const group = {
    id: logType,
    content: makeGroupLabel(logType, title),
    className: "custom-group-label",
    order: 1,
  };
  const items = processData(logType, logs);
  const options = buildFixedHeightOptions(range, 76);

  if (logs.length === 0) {
    return (
      <ObserverEmptyState
        title={title}
        message={`${title} 이력이 없습니다`}
      />
    );
  }

  return (
    <BaseObserver
      groups={[group]}
      items={items}
      options={options}
      title={title}
      showTimeAxis={showTimeAxis}
      headerExtra={
        showLegend ? <ObserverLegend items={observerLegends[logType]} /> : null
      }
    />
  );
}
