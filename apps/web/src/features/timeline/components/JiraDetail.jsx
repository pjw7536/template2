// src/features/timeline/components/logDetail/JiraDetail.jsx
import React from "react";
import Field from "./Field";
import UrlField from "./UrlField";

export default function JiraDetail({ log }) {
  return (
    <>
      <Field label="ID" value={log.id} />
      <Field label="Log Type" value={log.logType} />
      <Field label="Issue Status" value={log.eventType} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Issue Key" value={log.issueKey} />
      <Field label="Assignee" value={log.assignee} />
      <Field label="Priority" value={log.priority} />
      <Field label="Reporter" value={log.reporter} />
      <Field label="Summary" value={log.summary} className="col-span-2" />
      <Field
        label="Description"
        value={log.description}
        className="col-span-2"
      />
      <UrlField url={log.url} />
    </>
  );
}
