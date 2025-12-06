// src/features/timeline/components/logDetail/TipDetail.jsx
import React from "react";
import Field from "./Field";
import UrlField from "./UrlField";

export default function TipDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="TIP Event" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Level" value={log.level} />
      <Field label="Comment" value={log.comment} className="col-span-2" />
      <UrlField url={log.url} />
    </>
  );
}
