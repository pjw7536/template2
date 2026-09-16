import React from "react";
import Field from "./Field";

export default function InterlockDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="Line" value={log.lineId} />
      <Field label="Interlock Type" value={log.interlockType} />
      <Field label="Area" value={log.areaName} />
      <Field label="Process" value={log.processId} />
      <Field label="EQP" value={log.prodEqpId || log.eqpId} />
      <Field label="Metro EQP" value={log.metroEqpId} />
      <Field label="Time" value={log.eventTime} />
      <Field label="PPID" value={log.ppid} />
      <Field label="Production Step" value={log.prodStepSeq} />
      <Field label="Metro Step" value={log.metroStepSeq} />
      <Field label="Metro Item" value={log.metroItem} />
      <Field label="Lot" value={log.lotId} />
      <Field label="Wafer" value={log.waferId} />
      <Field label="LSL / Target / USL" value={[log.lsl, log.specTarget, log.usl].map((value) => value ?? "-").join(" / ")} />
      <Field label="LCL / CL / UCL" value={[log.lcl, log.cl, log.ucl].map((value) => value ?? "-").join(" / ")} />
      <Field label="Item Value" value={log.itemValue} />
      <Field label="Interlock Comment" value={log.interlockComment} fullWidth />
      <Field label="EQP Detail Comment" value={log.eqpDetailComment} fullWidth />
      <Field label="Engineer Comment" value={log.engrComment} fullWidth />
    </>
  );
}
