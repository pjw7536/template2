// src/features/timeline/components/logDetail/CtttmDetail.jsx
import React from "react";
import Field from "./Field";

export default function CtttmDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="CTTTM" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Recipe" value={log.recipe} />
      <Field label="Operator" value={log.operator} />
      <Field label="Duration" value={log.duration?.toFixed(1)} />
      <Field
        label="Comment"
        value={log.comment}
        className="col-span-2"
        streaming={true}
      />
    </>
  );
}
