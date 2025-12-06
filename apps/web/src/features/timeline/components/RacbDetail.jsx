// src/features/timeline/components/logDetail/RacbDetail.jsx
import React from "react";
import Field from "./Field";
import UrlField from "./UrlField";

export default function RacbDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="RACB Alarm" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Operator" value={log.operator} />
      <Field label="Comment" value={log.comment} className="col-span-2" />
      <UrlField url={log.url} />
    </>
  );
}
