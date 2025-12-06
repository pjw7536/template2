// src/features/timeline/components/logDetail/EqpDetail.jsx
import React from "react";
import Field from "./Field";

export default function EqpDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="EQP State" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="End Time" value={log.endTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Duration" value={log.duration?.toFixed(1)} />
      <Field label="Comment" value={log.comment} className="col-span-2" />
    </>
  );
}
