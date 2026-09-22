import { CHART_MARKER_SIZE, EQC_TIME_STATUS_MARKER, STATUS_MARKER, STATUS_ORDER } from "../utils/chartStatus"

const NCOLS = 3
const EQC_TIME_NCOLS = 1
const SUBPLOT_H = 340
const SUBPLOT_H_WAFER = 420
const AXIS_FONT_SIZE = 12
const SUBPLOT_TITLE_FONT_SIZE = 13
const AXIS_TITLE_FONT_SIZE = 12
const RISK_TITLE_MARKER = '<span style="color:#be123c;font-size:19px">▌</span>'
const RISK_BADGE_XSHIFT = -62
const RISK_TITLE_START_X = 0.16
const X_JITTER_OFFSET = 0.28
const MAX_X_TICKS_PER_SUBPLOT = 12
const MAX_POINTS_PER_SUBPLOT = 900
const OVERSCAN_ROWS = 3
const DEFAULT_VIEWPORT_H = 1200
// idle 스케줄러(정상 마커 fill-in을 유휴 시점으로 미룸). requestIdleCallback 미지원 시 setTimeout 폴백.
const scheduleIdle = (typeof window !== 'undefined' && window.requestIdleCallback)
  ? (cb) => window.requestIdleCallback(cb, { timeout: 250 })
  : (cb) => window.setTimeout(cb, 32)
const cancelIdle = (typeof window !== 'undefined' && window.cancelIdleCallback)
  ? (h) => window.cancelIdleCallback(h)
  : (h) => window.clearTimeout(h)
const LASSO_KEY_SEPARATOR = '\u0000'
const HIGHLIGHT_COLOR = '#14DBFF'
const HIGHLIGHT_GLOW = 'rgba(20, 219, 255, 0.28)'
const HIGHLIGHT_SHINE = '#89FCFF'
const HOVER_LABEL = { align: 'left' }
const EQC_COLOR_PALETTE = [
  '#2563eb', '#16a34a', '#f97316', '#7c3aed', '#0891b2',
  '#db2777', '#65a30d', '#9333ea', '#0f766e', '#ca8a04',
  '#1d4ed8', '#be123c',
]

const ACTIVE_MODEBAR_TITLES = new Set(['Pan', 'Box select wafer', 'Box select lot'])
const PRESERVE_ACTIVE_MODEBAR_TITLES = new Set(['Autoscale', 'Reset axes'])

const HAND_PAN_ICON = {
  width: 512, height: 512,
  path: 'M176 232V96c0-22 18-40 40-40s40 18 40 40v120h16V56c0-22 18-40 40-40s40 18 40 40v176h16V88c0-22 18-40 40-40s40 18 40 40v184h16V144c0-22 18-40 40-40s40 18 40 40v176c0 93-75 168-168 168h-56c-56 0-108-28-139-75L48 334c-13-20-8-47 12-60s47-8 60 12l40 60V232c0-22 18-40 40-40s40 18 40 40z',
}

const LASSO_WAFER_ICON = {
  width: 512, height: 512,
  path: 'M254 72c104 0 188 57 188 128s-84 128-188 128S66 271 66 200 150 72 254 72zm0 52c-72 0-132 35-132 76s60 76 132 76 132-35 132-76-60-76-132-76zm-34 252h68v68h-68z',
}

const LASSO_LOT_ICON = {
  width: 512, height: 512,
  path: 'M254 72c104 0 188 57 188 128s-84 128-188 128S66 271 66 200 150 72 254 72zm0 52c-72 0-132 35-132 76s60 76 132 76 132-35 132-76-60-76-132-76zM154 366h58v58h-58zm73 0h58v58h-58zm73 0h58v58h-58z',
}

function getActiveModebarTitle(dragMode, lassoMode, lassoShape) {
  if (dragMode === 'pan') return 'Pan'
  if (dragMode === 'select' && lassoShape === 'box') {
    if (lassoMode === 'wafer') return 'Box select wafer'
    if (lassoMode === 'lot') return 'Box select lot'
  }
  return null
}

function syncModebarActiveButtons(plotEl, activeTitle) {
  plotEl.querySelectorAll('.modebar-btn[data-title]').forEach(button => {
    const title = button.getAttribute('data-title')
    if (!title || !ACTIVE_MODEBAR_TITLES.has(title)) return
    const active = title === activeTitle
    button.classList.toggle('active', active)
    button.setAttribute('aria-pressed', active ? 'true' : 'false')
  })
}

function parseTimeMs(value) {
  const ms = new Date(value).getTime()
  return Number.isFinite(ms) ? ms : 0
}

function formatAxisTime(value) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return value
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function getWaferJitterOffset(waferId) {
  const waferNo = Number.parseInt(waferId, 10)
  if (Number.isFinite(waferNo)) {
    const clamped = Math.max(1, Math.min(25, waferNo))
    return ((clamped - 13) / 12) * X_JITTER_OFFSET
  }
  let hash = 0
  for (let i = 0; i < waferId.length; i += 1) hash = (hash * 31 + waferId.charCodeAt(i)) % 997
  return ((hash / 996) * 2 - 1) * X_JITTER_OFFSET
}

function buildTimeXAxis(subData) {
  const xByRow = new Map()
  subData.forEach(d => xByRow.set(d, d.tkinTime))
  const times = subData.map(d => d.tkinTime)
  const lineMin = times.reduce((a, b) => a < b ? a : b)
  const lineMax = times.reduce((a, b) => a > b ? a : b)
  return {
    axis: {
      title: { text: 'eqp_tkin_time', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 10 },
      type: 'date',
      tickformat: '%m-%d',
      nticks: MAX_X_TICKS_PER_SUBPLOT,
      tickangle: -90,
    },
    xByRow, lineMin, lineMax,
  }
}

function buildWaferXAxis(subData) {
  const sorted = [...subData].sort((a, b) => {
    const byTime = parseTimeMs(a.tkinTime) - parseTimeMs(b.tkinTime)
    if (byTime !== 0) return byTime
    return a.waferId.localeCompare(b.waferId, undefined, { numeric: true })
  })
  const xByRow = new Map()
  sorted.forEach((d, idx) => xByRow.set(d, idx + getWaferJitterOffset(d.waferId)))
  const step = Math.max(1, Math.ceil(sorted.length / MAX_X_TICKS_PER_SUBPLOT))
  const sampled = sorted.filter((_, idx) => idx % step === 0)
  return {
    axis: {
      title: { text: 'eqp_tkin_time, wafer_id', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 12 },
      type: 'linear',
      tickmode: 'array',
      tickangle: -90,
      range: [-0.7, Math.max(sorted.length - 0.3, 0.7)],
      tickvals: sampled.map(d => sorted.indexOf(d)),
      ticktext: sampled.map(d => `${formatAxisTime(d.tkinTime)}_${d.waferId}`),
    },
    xByRow,
    lineMin: -0.5,
    lineMax: Math.max(sorted.length - 0.5, 0.5),
  }
}

function buildXAxis(subData, mode) {
  return mode === 'tkin_time_wafer_id' ? buildWaferXAxis(subData) : buildTimeXAxis(subData)
}

function buildEqcTimeXAxis(subData) {
  const sorted = [...subData].sort((a, b) => {
    const byEqc = a.eqc.localeCompare(b.eqc, undefined, { numeric: true })
    if (byEqc !== 0) return byEqc
    const byTime = parseTimeMs(a.tkinTime) - parseTimeMs(b.tkinTime)
    if (byTime !== 0) return byTime
    return a.waferId.localeCompare(b.waferId, undefined, { numeric: true })
  })
  const xByRow = new Map()
  const eqcOrder = [...new Set(sorted.map(d => d.eqc))]
  const eqcColor = new Map(eqcOrder.map((eqc, idx) => [eqc, EQC_COLOR_PALETTE[idx % EQC_COLOR_PALETTE.length]]))
  const boundaries = []
  const tickvals = []
  const ticktext = []

  let cursor = 0
  eqcOrder.forEach((eqc, eqcIdx) => {
    const rows = sorted.filter(d => d.eqc === eqc)
    const start = cursor
    rows.forEach((row, idx) => xByRow.set(row, start + idx))
    cursor += rows.length
    const end = cursor - 1
    tickvals.push((start + end) / 2)
    ticktext.push(eqc)
    if (eqcIdx < eqcOrder.length - 1) boundaries.push(end + 0.5)
  })

  return {
    axis: {
      title: { text: 'eqpch, tkin_time', font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 12 },
      type: 'linear',
      tickmode: 'array',
      tickangle: -45,
      range: [-0.7, Math.max(sorted.length - 0.3, 0.7)],
      tickvals,
      ticktext,
    },
    xByRow,
    lineMin: -0.5,
    lineMax: Math.max(sorted.length - 0.5, 0.5),
    eqcOrder,
    eqcColor,
    boundaries,
  }
}

function sortHighlightFirst(keys, hasHighlight) {
  return [...keys].sort((a, b) => {
    const aRisk = hasHighlight(a)
    const bRisk = hasHighlight(b)
    if (aRisk === bRisk) return 0
    return aRisk ? -1 : 1
  })
}

function getBinNameAxisTitle(subData) {
  const binNames = [...new Set(subData.map(d => d.binName))].sort()
  return binNames.length > 0 ? binNames.join(', ') : ''
}

function sampleRowsForPlot(rows, maxPoints = MAX_POINTS_PER_SUBPLOT) {
  if (rows.length <= maxPoints) return rows
  const anomalyRows = rows.filter(d => d.displayStatus === 'High Risk Chamber' || d.displayStatus === 'Warning')
  const anomalySet = new Set(anomalyRows)
  const remainingBudget = Math.max(maxPoints - anomalyRows.length, Math.floor(maxPoints * 0.35))
  const normalRows = rows.filter(d => !anomalySet.has(d))
  const sampledNormal = []
  const step = normalRows.length / remainingBudget
  for (let i = 0; i < remainingBudget; i += 1) {
    const idx = Math.min(Math.floor(i * step), normalRows.length - 1)
    if (normalRows[idx]) sampledNormal.push(normalRows[idx])
  }
  return [...anomalyRows, ...sampledNormal]
}

function getWaferLassoKey(row) {
  return `${row.rootLotId}${LASSO_KEY_SEPARATOR}${row.waferId}`
}

function getLotLassoKey(row) {
  return row.lotId
}

function escapeHoverText(value) {
  if (!value) return ''
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function isLassoHighlighted(row, selection) {
  if (!selection) return false
  if (selection.mode === 'wafer') return selection.keys.has(getWaferLassoKey(row))
  return selection.keys.has(getLotLassoKey(row))
}

function getSelectedPointKeys(points, mode) {
  const keys = new Set()
  points.forEach(point => {
    const customdata = point.customdata
    if (!Array.isArray(customdata)) return
    const [rootLotId, lotId, waferId] = customdata
    if (mode === 'wafer' && rootLotId !== undefined && waferId !== undefined) {
      keys.add(`${rootLotId}${LASSO_KEY_SEPARATOR}${waferId}`)
    }
    if (mode === 'lot' && lotId !== undefined) keys.add(String(lotId))
  })
  return keys
}

function makeHighlightTrace(rows, xAxis, xRef, yRef, customdata, hovertemplate, layer) {
  const common = {
    type: 'scatter',
    mode: 'markers',
    x: rows.map(d => xAxis.xByRow.get(d) ?? 0),
    y: rows.map(d => d.binValue),
    customdata,
    xaxis: xRef,
    yaxis: yRef,
    showlegend: false,
    hovertemplate,
  }

  if (layer === 'glow') {
    return {
      ...common,
      marker: {
        color: HIGHLIGHT_GLOW,
        size: CHART_MARKER_SIZE + 12,
        symbol: 'circle',
        opacity: 0.9,
        line: { color: 'rgba(20, 219, 255, 0)', width: 0 },
      },
      hoverinfo: 'skip',
    }
  }

  if (layer === 'shine') {
    return {
      ...common,
      marker: {
        color: HIGHLIGHT_SHINE,
        size: Math.max(CHART_MARKER_SIZE - 2, 5),
        symbol: 'circle',
        opacity: 0.92,
        line: { color: 'rgba(137, 252, 255, 0)', width: 0 },
      },
      hoverinfo: 'skip',
    }
  }

  return {
    ...common,
    marker: {
      color: HIGHLIGHT_COLOR,
      size: CHART_MARKER_SIZE + 7,
      symbol: 'circle',
      opacity: 1,
      line: { color: 'rgba(20, 219, 255, 0)', width: 0 },
    },
    name: 'selected highlight',
  }
}

function makePointCustomData(rows, includeEqc = false) {
  return rows.map(d => [
    d.rootLotId,
    d.lotId,
    d.waferId,
    d.tkinTime,
    escapeHoverText(d.comment),
    ...(includeEqc ? [d.eqc] : []),
  ])
}

function getStepPpidTitle(rows) {
  const stepSeqs = [...new Set(rows.map(d => d.stepSeq))].sort()
  const ppids = [...new Set(rows.map(d => d.ppid))].sort()
  return `${stepSeqs.length > 0 ? stepSeqs.join(', ') : '-'} / ${ppids.length > 0 ? ppids.join(', ') : '-'}`
}

function getUniqueText(values) {
  const unique = [...new Set(values)].sort()
  return unique.length > 0 ? unique.join(', ') : '-'
}

function getSharedYRange(rows) {
  if (!rows.length) return null
  const vals = rows.map(d => d.binValue)
  const limits = rows
    .map(d => d.propOver50 < 0.5 ? d.usl : d.lsl)
    .filter(v => v !== null && v !== undefined)
  const allY = [...vals, ...limits]
  const yMin = Math.min(...allY)
  const yMax = Math.max(...allY)
  const pad = Math.max((yMax - yMin) * 0.1, 1)
  return [yMin - pad, yMax + pad]
}

function getLimitInfoFromRows(rows) {
  if (!rows.length) return { value: null, label: '', color: '' }
  const r = rows[0]
  const isMso = r.propOver50 < 0.5
  const val = isMso ? r.usl : r.lsl
  return { value: val ?? null, label: isMso ? 'USL' : 'LSL', color: '#dc2626' }
}

function getBaseXAxis() {
  return {
    color: '#6b7394',
    showgrid: false,
    zeroline: false,
    linecolor: '#000000',
    linewidth: 1,
    mirror: true,
    tickfont: { size: AXIS_FONT_SIZE, color: '#6b7394' },
    ticks: 'outside',
    ticklen: 5,
    tickwidth: 1,
    tickcolor: '#000000',
    showticklabels: true,
    automargin: true,
    showline: true,
  }
}

function getBaseYAxis() {
  return {
    color: '#6b7394',
    showgrid: true,
    gridcolor: '#c7c7c7',
    griddash: 'dot',
    zeroline: false,
    linecolor: '#000000',
    linewidth: 1,
    mirror: true,
    tickfont: { size: AXIS_FONT_SIZE, color: '#6b7394' },
    ticks: 'outside',
    ticklen: 5,
    tickwidth: 1,
    tickcolor: '#000000',
    title: { font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
    showticklabels: true,
    nticks: 12,
    automargin: true,
    showline: true,
  }
}

function buildSingleEqcTimeChart(key, subData, lassoSelection) {
  const plotData = []
  const shapes = []
  const annotations = []
  const xAxis = buildEqcTimeXAxis(subData)
  const plotRows = sampleRowsForPlot(
    subData,
    Math.max(MAX_POINTS_PER_SUBPLOT * xAxis.eqcOrder.length, MAX_POINTS_PER_SUBPLOT),
  )
  const title = getStepPpidTitle(subData)
  const yRange = getSharedYRange(subData)

  xAxis.boundaries.forEach(x => {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: x, x1: x,
      y0: yRange?.[0] ?? 0,
      y1: yRange?.[1] ?? 1,
      line: { color: '#94a3b8', dash: 'dot', width: 1 },
    })
  })

  STATUS_ORDER.forEach(status => {
    xAxis.eqcOrder.forEach(eqc => {
      const pts = plotRows.filter(d => d.displayStatus === status && d.eqc === eqc)
      if (pts.length === 0) return

      const highlightedPts = lassoSelection
        ? subData.filter(d => d.displayStatus === status && d.eqc === eqc && isLassoHighlighted(d, lassoSelection))
        : []
      const markerStyle = EQC_TIME_STATUS_MARKER[status]
      const eqcColor = xAxis.eqcColor.get(eqc) ?? '#2563eb'
      const hovertemplate =
        `<b>${title}</b><br>` +
        `eqc: %{customdata[5]}<br>` +
        `Time: %{customdata[3]}<br>` +
        `Value: %{y:.4f}<br>` +
        `root_lot_id: %{customdata[0]}<br>` +
        `lot_id: %{customdata[1]}<br>` +
        `wafer_id: %{customdata[2]}<br>` +
        `comment: %{customdata[4]}<br>` +
        `${status}<extra></extra>`
      const customdata = makePointCustomData(pts, true)

      plotData.push({
        type: 'scatter', mode: 'markers',
        x: pts.map(d => xAxis.xByRow.get(d) ?? 0),
        y: pts.map(d => d.binValue),
        customdata,
        marker: { color: eqcColor, size: CHART_MARKER_SIZE, symbol: markerStyle.symbol, opacity: 0.95, line: { color: eqcColor, width: 1.4 } },
        name: markerStyle.label,
        legendgroup: status,
        showlegend: false,
        hovertemplate,
      })

      if (highlightedPts.length > 0) {
        const highlightCustomData = makePointCustomData(highlightedPts, true)
        plotData.push(
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'glow'),
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'sphere'),
          makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'shine'),
        )
      }
    })
  })

  const limit = getLimitInfoFromRows(subData)
  if (limit.value !== null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: xAxis.lineMin, x1: xAxis.lineMax,
      y0: limit.value, y1: limit.value,
      line: { color: limit.color, dash: 'dot', width: 1.5 },
    })
    annotations.push({
      xref: 'x domain', yref: 'y',
      x: 1, y: limit.value,
      text: `<b>${limit.label}</b>`,
      showarrow: false,
      font: { size: 9, color: limit.color },
      xanchor: 'right', yanchor: 'bottom',
    })
  }

  annotations.push({
    xref: 'x domain', yref: 'y domain',
    x: 0.5, y: 1.065,
    text: `<b>${title}</b>`,
    showarrow: false,
    font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#1a2044' },
    xanchor: 'center', yanchor: 'bottom',
  })

  return {
    key,
    plotData,
    plotLayout: {
      xaxis: { ...getBaseXAxis(), ...xAxis.axis },
      yaxis: {
        ...getBaseYAxis(),
        title: { text: getBinNameAxisTitle(subData), font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
        ...(yRange !== null ? { range: yRange.slice(), autorange: false } : { autorange: true }),
      },
      height: SUBPLOT_H_WAFER,
      autosize: true,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#6b7394', size: AXIS_FONT_SIZE },
      margin: { l: 62, r: 20, t: 55, b: 115 },
      shapes, annotations,
      hoverlabel: HOVER_LABEL,
      showlegend: false,
    },
  }
}

function buildSingleStandardChart(key, subData, title, limit, sharedYRange, xAxisMode, lassoSelection) {
  const plotData = []
  const baseData = []  // 이상(비정상) 트레이스만 — progressive draw의 1단계
  const shapes = []
  const annotations = []
  const hasRisk = subData.some(d => d.displayStatus === 'High Risk Chamber')
  const xAxis = buildXAxis(subData, xAxisMode)
  const plotRows = sampleRowsForPlot(subData)

  STATUS_ORDER.forEach(status => {
    const pts = plotRows.filter(d => d.displayStatus === status)
    if (pts.length === 0) return

    const highlightedPts = lassoSelection
      ? subData.filter(d => d.displayStatus === status && isLassoHighlighted(d, lassoSelection))
      : []
    const markerStyle = STATUS_MARKER[status]
    const hovertemplate =
      `<b>${title}</b><br>` +
      `Time: %{customdata[3]}<br>` +
      `Value: %{y:.4f}<br>` +
      `root_lot_id: %{customdata[0]}<br>` +
      `lot_id: %{customdata[1]}<br>` +
      `wafer_id: %{customdata[2]}<br>` +
      `comment: %{customdata[4]}<br>` +
      `${status}<extra></extra>`
    const customdata = makePointCustomData(pts)

    const isAnomaly = status !== 'Normal (Ref)'
    const mainTrace = {
      type: 'scatter', mode: 'markers',
      x: pts.map(d => xAxis.xByRow.get(d) ?? 0),
      y: pts.map(d => d.binValue),
      customdata,
      marker: { color: markerStyle.color, size: CHART_MARKER_SIZE, symbol: markerStyle.symbol, opacity: 0.95, line: { color: markerStyle.color, width: 1.2 } },
      name: markerStyle.label,
      legendgroup: status,
      showlegend: false,
      hovertemplate,
    }
    plotData.push(mainTrace)
    if (isAnomaly) baseData.push(mainTrace)

    if (highlightedPts.length > 0) {
      const highlightCustomData = makePointCustomData(highlightedPts)
      const highlightTraces = [
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'glow'),
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'sphere'),
        makeHighlightTrace(highlightedPts, xAxis, 'x', 'y', highlightCustomData, hovertemplate, 'shine'),
      ]
      plotData.push(...highlightTraces)
      if (isAnomaly) baseData.push(...highlightTraces)
    }
  })

  if (limit.value !== null) {
    shapes.push({
      type: 'line', xref: 'x', yref: 'y',
      x0: xAxis.lineMin, x1: xAxis.lineMax,
      y0: limit.value, y1: limit.value,
      line: { color: limit.color, dash: 'dot', width: 1.5 },
    })
    annotations.push({
      xref: 'x domain', yref: 'y',
      x: 1, y: limit.value,
      text: `<b>${limit.label}</b>`,
      showarrow: false,
      font: { size: 9, color: limit.color },
      xanchor: 'right', yanchor: 'bottom',
    })
  }

  if (hasRisk) {
    annotations.push({
      xref: 'paper', yref: 'paper',
      x: 0, y: 1.065,
      text: `${RISK_TITLE_MARKER} <b><span style="color:#be123c">High Risk</span></b>`,
      showarrow: false,
      font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#be123c' },
      xshift: RISK_BADGE_XSHIFT,
      xanchor: 'left', yanchor: 'bottom',
    })
  }

  annotations.push({
    xref: 'x domain', yref: 'y domain',
    x: hasRisk ? RISK_TITLE_START_X : 0.5,
    y: 1.065,
    text: `<b>${title}</b>`,
    showarrow: false,
    font: { size: SUBPLOT_TITLE_FONT_SIZE, color: '#1a2044' },
    xanchor: hasRisk ? 'left' : 'center', yanchor: 'bottom',
  })

  return {
    key,
    plotData,
    // progressive draw: 이상 트레이스가 있고 정상 트레이스도 있을 때만 1단계용 baseData 제공.
    // (전부 정상이거나 전부 이상이면 나눌 필요 없어 undefined → 전체를 즉시 그림)
    baseData: (baseData.length > 0 && baseData.length < plotData.length) ? baseData : undefined,
    plotLayout: {
      xaxis: { ...getBaseXAxis(), ...xAxis.axis },
      yaxis: {
        ...getBaseYAxis(),
        title: { text: getBinNameAxisTitle(subData), font: { size: AXIS_TITLE_FONT_SIZE, color: '#4b5578' }, standoff: 8 },
        // sharedYRange는 모든 subplot이 공유하는 배열이다. Plotly가 layout을 in-place로 변형
        // (확대 시 range 덮어쓰기)하므로, 복사본을 넘겨 한 차트의 줌이 다른 차트로 새지 않게 한다.
        ...(sharedYRange !== null ? { range: sharedYRange.slice(), autorange: false } : { autorange: true }),
      },
      height: xAxisMode === 'tkin_time_wafer_id' ? SUBPLOT_H_WAFER : SUBPLOT_H,
      autosize: true,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#6b7394', size: AXIS_FONT_SIZE },
      margin: { l: 70, r: 20, t: 50, b: xAxisMode === 'tkin_time_wafer_id' ? 130 : 75 },
      shapes, annotations,
      hoverlabel: HOVER_LABEL,
      showlegend: false,
    },
  }
}


export {
  ACTIVE_MODEBAR_TITLES,
  DEFAULT_VIEWPORT_H,
  EQC_TIME_NCOLS,
  HAND_PAN_ICON,
  LASSO_LOT_ICON,
  LASSO_WAFER_ICON,
  NCOLS,
  OVERSCAN_ROWS,
  PRESERVE_ACTIVE_MODEBAR_TITLES,
  SUBPLOT_H,
  SUBPLOT_H_WAFER,
  buildSingleEqcTimeChart,
  buildSingleStandardChart,
  cancelIdle,
  getActiveModebarTitle,
  getLimitInfoFromRows,
  getSelectedPointKeys,
  getSharedYRange,
  getStepPpidTitle,
  getUniqueText,
  scheduleIdle,
  sortHighlightFirst,
  syncModebarActiveButtons,
}
