import React from "react";
import Field from "./Field";

export default function InterlockDetail({ log }) {
  return (
    <>
      <Field label="Log Type" value={log.logType} />
      <Field label="Interlock Kind" value={log.interlockKind} />
      <Field label="Time" value={log.eventTime} />
      <Field label="Interlock No" value={log.interlockNo} />
      <Field label="Interlock Type" value={log.interlockType} />
      <Field label="Item Value" value={log.itemValue} />
      <Field label="Production EQP" value={log.prodEqpId || log.eqpId} />
      <Field label="Production Chamber" value={log.prodChamberId} />
      <Field label="Metro EQP" value={log.metroEqpId} />
      <Field label="Line" value={log.lineId} />
      <Field label="Area" value={log.areaName} />
      <Field label="Process" value={log.processId} />
      <Field label="PPID" value={log.ppid} />
      <Field label="Production Step" value={log.prodStepSeq} />
      <Field label="Metro Step" value={log.metroStepSeq} />
      <Field label="Metro Item" value={log.metroItem} />
      <Field label="Lot" value={log.lotId} />
      <Field label="Batch" value={log.batchId} />
      <Field label="Wafer" value={log.waferId} />
      <Field label="LSL / Target / USL" value={[log.lsl, log.specTarget, log.usl].map((value) => value ?? "-").join(" / ")} />
      <Field label="LCL / CL / UCL" value={[log.lcl, log.cl, log.ucl].map((value) => value ?? "-").join(" / ")} />
      <Field label="EQP Type" value={log.prodEqpType} />
      <Field label="EQP Process Phase" value={log.eqpProcessPhase} />
      <Field label="Production Bay" value={log.prodBayName} />
      <Field label="Production Time (KST)" value={log.prodProgsTime} />
      <Field label="Metro Time" value={log.metroProgsTime} />
      <Field label="Occurrence Week" value={log.intlkOccurWeek} />
      <Field label="Occurrence Year/Month" value={log.intlkOccurYearM} />
      <Field label="Last Update" value={log.lastUpdateDate} />
      <Field label="Source ID" value={log.sourceId} />
      <Field label="Interlock Description" value={log.interlockDesc} fullWidth />
      <Field label="Interlock Comment" value={log.interlockComment} fullWidth />
      <Field label="EQP Detail Comment" value={log.eqpDetailComment} fullWidth />
      <Field label="Engineer Comment" value={log.engrComment} fullWidth />
    </>
  );
}
