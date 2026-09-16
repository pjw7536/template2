// 파일 경로: src/features/tttm-spider/utils/selection.js
// TTTM Spider REF/COMP 선택 상태 유틸입니다.

export function createEmptyChamber() {
  return { line: "", eqp: "", chamber: "", date: "" }
}

export function createEmptyComp() {
  return { line: "", eqp: "", chamber: "", date: "", type: "" }
}

export function isChamberComplete(sel) {
  return Boolean(sel && sel.line && sel.eqp && sel.chamber && sel.date)
}

export function isCompComplete(comp) {
  return isChamberComplete(comp) && Boolean(comp.type)
}

export function isRefCompReady(ref, comp, dataType) {
  return isChamberComplete(ref) && isCompComplete(comp) && Boolean(dataType)
}

// 자가비교(REF==COMP): 프론트에서 배지로 안내하기 위한 감지. 백엔드도 동일 판단.
export function isSelfComparison(ref, comp) {
  const keys = ["line", "eqp", "chamber", "date"]
  return keys.every((k) => String(ref?.[k] ?? "") === String(comp?.[k] ?? ""))
}

export function buildDashboardPayload({ ref, comp, dataType, stage, oesMethod, traceRecipeId }) {
  return {
    comp: { line: comp.line, eqp: comp.eqp, chamber: comp.chamber, date: comp.date, type: comp.type },
    ref: { line: ref.line, eqp: ref.eqp, chamber: ref.chamber, date: ref.date },
    dataType,
    stage: stage || "P3",
    oesMethod: oesMethod || "oob",
    ...(traceRecipeId ? { traceRecipeId } : {}),
  }
}

export function buildSelectionKey(payload) {
  return payload ? JSON.stringify(payload) : ""
}

// multi-COMP: (ref, comp, dataType) 하나를 식별하는 키.
export function compEntryKey(ref, comp, dataType) {
  const r = [ref.line, ref.eqp, ref.chamber, ref.date].join("|")
  const c = [comp.line, comp.eqp, comp.chamber, comp.date, comp.type].join("|")
  return `${r}::${c}::${dataType}`
}

// 챔버 칩 라벨.
export function compEntryLabel(comp) {
  return `${comp.eqp}-${comp.chamber}`
}

// 여러 배열의 교집합(정렬 유지). COMP 날짜를 체크된 챔버 공통으로 좁힐 때 사용.
export function intersectLists(lists) {
  if (!lists.length) return []
  return lists.reduce((acc, list) => acc.filter((x) => list.includes(x)))
}

// ── lotwf(웨이퍼) 선택 ──────────────────────────────────────────────────────
export function lotwfKey(l) {
  return [l.line, l.eqp, l.chamber, l.date, l.lot_id, l.slot_no].join("|")
}

// lotwf 가 속한 (line,eqp,chamber,date) 챔버-주기 키.
export function chamberKeyOfLotwf(l) {
  return [l.line, l.eqp, l.chamber, l.date].join("|")
}

function chamberOfLotwf(l) {
  return { line: l.line, eqp: l.eqp, chamber: l.chamber, date: l.date }
}

function groupByKey(arr, keyFn) {
  const m = {}
  for (const x of arr) { const k = keyFn(x); (m[k] ??= []).push(x) }
  return m
}

// 행(ROW) 모델: rows=[{comp:{eqp,chamber}|null, ref:{eqp,chamber}|null}].
// 각 행에서 comp/ref 둘 다 지정되고 각자 선택된 lotwf 가 있으면 하나의 비교(REFn vs COMPn).
export function buildEntriesFromRows(rows, compLotwf, refLotwf, type = "process") {
  const entries = []
  let idx = 0
  for (const row of rows) {
    if (!row.comp || !row.ref) continue
    const compSel = compLotwf.filter((l) => l.eqp === row.comp.eqp && l.chamber === row.comp.chamber)
    const refSel = refLotwf.filter((l) => l.eqp === row.ref.eqp && l.chamber === row.ref.chamber)
    if (!compSel.length || !refSel.length) continue
    idx += 1
    const c0 = compSel[0]
    const r0 = refSel[0]
    const comp = { line: c0.line, eqp: c0.eqp, chamber: c0.chamber, date: c0.date, type }
    const ref = { line: r0.line, eqp: r0.eqp, chamber: r0.chamber, date: r0.date }
    const recipe = c0.recipe_id ?? null
    entries.push({
      key: `${compEntryKey(ref, comp, "")}::${recipe ?? ""}::${idx}`,
      ref, comp, recipe, index: idx, name: `COMP${idx}`,
      compName: `${comp.eqp}·${comp.chamber}[${comp.date}]${recipe ? ` ${recipe}` : ""}`,
      refName: `${ref.eqp}·${ref.chamber}[${ref.date}]`,
      label: `REF${idx} vs COMP${idx}`,
    })
  }
  return { entries }
}

// 선택된 comp/ref lotwf → 대시보드 entries([{key,ref,comp,recipe,label,...}]).
// comp 는 (챔버·주기)별로 여러 COMP 로 split. ref 페어링:
//   shared=true  → 모든 COMP 가 동일한 단일 REF (REF vs COMP1, COMP2 …)
//   shared=false → COMP 챔버(PM) 기준으로 매칭된 개별 REF (REF1 vs COMP1, REF2 vs COMP2)
export function buildEntriesFromSelection(compLotwf, refLotwf, opts = {}) {
  const { type = "process", shared = false } = opts
  const compGroups = groupByKey(compLotwf, chamberKeyOfLotwf)
  const refGroups = Object.values(groupByKey(refLotwf, chamberKeyOfLotwf))
  if (!refGroups.length) return { entries: [], ref: null }

  const refByPM = {}
  for (const g of refGroups) { const pm = g[0].chamber; if (!refByPM[pm]) refByPM[pm] = g }
  const refFirst = refGroups[0]

  const entries = []
  let idx = 0
  for (const group of Object.values(compGroups)) {
    idx += 1
    const c0 = group[0]
    const refGroup = shared ? refFirst : (refByPM[c0.chamber] ?? refFirst)
    const r0 = refGroup[0]
    const comp = { line: c0.line, eqp: c0.eqp, chamber: c0.chamber, date: c0.date, type }
    const ref = chamberOfLotwf(r0)
    const recipe = c0.recipe_id ?? null
    entries.push({
      key: `${compEntryKey(ref, comp, "")}::${recipe ?? ""}`,
      ref, comp, recipe, index: idx, name: `COMP${idx}`,
      compName: `${comp.eqp}·${comp.chamber}[${comp.date}]${recipe ? ` ${recipe}` : ""}`,
      refName: `${ref.eqp}·${ref.chamber}[${ref.date}]`,
      label: shared ? `REF vs COMP${idx}` : `REF${idx} vs COMP${idx}`,
    })
  }
  return { entries, ref: chamberOfLotwf(refFirst[0]) }
}
