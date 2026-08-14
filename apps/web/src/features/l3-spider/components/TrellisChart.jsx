import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import {
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
} from "./trellisChartBuilders"
import './TrellisChart.css'

const FacetPlot = memo(function FacetPlot({ chart, lassoMode, lassoShape, dragMode, onSelected, onPanRequest, onLassoRequest, onModebarNeutralRequest }) {
  const plotRef = useRef(null)
  const initializedRef = useRef(false)
  const selectedHandlerRef = useRef(null)
  const deferHandleRef = useRef(0)
  const axisSigRef = useRef(null)
  const activeModebarTitle = getActiveModebarTitle(dragMode, lassoMode, lassoShape)

  useEffect(() => {
    const plotEl = plotRef.current
    if (!plotEl) return

    let disposed = false
    const syncActiveModebar = () => {
      if (!disposed) syncModebarActiveButtons(plotEl, activeModebarTitle)
    }
    const scheduleActiveModebarSync = () => {
      window.requestAnimationFrame(syncActiveModebar)
      window.setTimeout(syncActiveModebar, 0)
      window.setTimeout(syncActiveModebar, 80)
    }
    const modebarClickHandler = (event) => {
      if (!(event.target instanceof Element)) return
      const button = event.target.closest('.modebar-btn[data-title]')
      if (!button || !plotEl.contains(button)) return
      const title = button.getAttribute('data-title')
      if (title && ACTIVE_MODEBAR_TITLES.has(title)) return
      if (!title || !PRESERVE_ACTIVE_MODEBAR_TITLES.has(title)) {
        onModebarNeutralRequest()
        syncModebarActiveButtons(plotEl, null)
        return
      }
      scheduleActiveModebarSync()
    }

    const plotConfig = {
      responsive: true,
      displayModeBar: true,
      modeBarButtonsToRemove: ['pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d'],
      modeBarButtonsToAdd: [
        {
          name: 'pan-hand',
          title: 'Pan',
          icon: HAND_PAN_ICON,
          click: (gd) => {
            onPanRequest()
            Plotly.relayout(gd, { dragmode: 'pan' })
            syncModebarActiveButtons(gd, 'Pan')
          },
        },
        {
          name: 'lasso-wafer',
          title: 'Box select wafer',
          icon: LASSO_WAFER_ICON,
          click: (gd) => {
            onLassoRequest('wafer')
            Plotly.relayout(gd, { dragmode: 'select' })
            syncModebarActiveButtons(gd, 'Box select wafer')
          },
        },
        {
          name: 'lasso-lot',
          title: 'Box select lot',
          icon: LASSO_LOT_ICON,
          click: (gd) => {
            onLassoRequest('lot')
            Plotly.relayout(gd, { dragmode: 'select' })
            syncModebarActiveButtons(gd, 'Box select lot')
          },
        },
      ],
      displaylogo: false,
    }

    const layout = {
      ...chart.plotLayout,
      dragmode: dragMode,
      ...(dragMode === 'select' ? { selectdirection: 'd' } : {}),
    }

    // 사용자 줌 보존: 축 기준(xaxis 구성 + yaxis range)이 그대로인 재렌더(라쏘 선택/모드바 등)에서는
    // 현재 그래프의 실제 축 범위를 유지해 줌이 풀리지 않게 한다. 축 기준 자체가 바뀌면(데이터/xAxis
    // 모드 변경 등) chart.plotLayout의 기본 범위를 그대로 적용(리셋).
    const axisSig = JSON.stringify([
      chart.plotLayout.xaxis,
      chart.plotLayout.yaxis?.range ?? null,
      chart.plotLayout.yaxis?.autorange ?? null,
    ])
    const axisBaseChanged = axisSigRef.current !== axisSig
    axisSigRef.current = axisSig
    if (initializedRef.current && !axisBaseChanged && plotEl.layout) {
      const cur = plotEl.layout
      if (cur.yaxis) {
        layout.yaxis = { ...layout.yaxis, autorange: cur.yaxis.autorange }
        if (cur.yaxis.range) layout.yaxis.range = cur.yaxis.range.slice()
      }
      if (cur.xaxis) {
        layout.xaxis = { ...layout.xaxis, autorange: cur.xaxis.autorange }
        if (cur.xaxis.range) layout.xaxis.range = cur.xaxis.range.slice()
      }
    }

    // progressive draw는 '최초 그릴 때(newPlot)'에만 적용: 이상 트레이스만 먼저 그리고 정상은
    // idle에 채운다. 이후 재렌더(모드바/드래그모드/데이터 변경 등)는 전체를 한 번에 그려
    // 매번 정상점이 사라졌다 다시 생기는 깜빡임을 방지한다.
    const usePartial = !initializedRef.current && Boolean(chart.baseData)
    const firstData = usePartial ? chart.baseData : chart.plotData
    plotEl.addEventListener('click', modebarClickHandler, true)
    const plotPromise = initializedRef.current
      ? Plotly.react(plotEl, firstData, layout, plotConfig)
      : Plotly.newPlot(plotEl, firstData, layout, plotConfig)

    initializedRef.current = true
    plotPromise.finally(() => {
      if (disposed) return
      syncActiveModebar()
      // 2단계: 정상 마커까지 포함한 전체를 idle(유휴) 시점에 채운다. (최초 그릴 때만)
      // 스크롤/다른 subplot 마운트로 메인스레드가 바쁘면 자연히 뒤로 밀려 fling이 가벼워진다.
      if (usePartial) {
        deferHandleRef.current = scheduleIdle(() => {
          deferHandleRef.current = 0
          if (disposed) return
          Plotly.react(plotEl, chart.plotData, layout, plotConfig).finally(() => {
            if (!disposed) syncActiveModebar()
          })
        })
      }
      if (selectedHandlerRef.current) {
        plotEl.removeListener?.('plotly_selected', selectedHandlerRef.current)
        selectedHandlerRef.current = null
      }
      if (lassoMode === 'off') return
      const selectedHandler = (event) => {
        onSelected(Array.isArray(event?.points) ? event.points : [])
      }
      selectedHandlerRef.current = selectedHandler
      plotEl.on?.('plotly_selected', selectedHandler)
    })

    return () => {
      disposed = true
      if (deferHandleRef.current) {
        cancelIdle(deferHandleRef.current)
        deferHandleRef.current = 0
      }
      plotEl.removeEventListener('click', modebarClickHandler, true)
      if (selectedHandlerRef.current) {
        plotEl.removeListener?.('plotly_selected', selectedHandlerRef.current)
        selectedHandlerRef.current = null
      }
    }
  }, [chart.plotData, chart.baseData, chart.plotLayout, lassoMode, lassoShape, dragMode, activeModebarTitle, onSelected, onPanRequest, onLassoRequest, onModebarNeutralRequest])

  useEffect(() => () => {
    const plotEl = plotRef.current
    if (plotEl && initializedRef.current) Plotly.purge(plotEl)
  }, [])

  return <div ref={plotRef} className="tc-plot" />
})

const TrellisChart = forwardRef(function TrellisChart({
  data,
  trellisBy,
  xAxisMode,
  highlightFirst = false,
  lassoMode = 'off',
  lassoShape = 'box',
  onLassoModeChange,
  onLassoShapeChange,
  scrollContainerRef,
  outerScrollTop = 0,
  outerViewportHeight = DEFAULT_VIEWPORT_H,
}, ref) {
  const scrollerRef = useRef(null)
  const spacerRef = useRef(null)
  const virtualWindowRef = useRef(null)
  const plotGridRef = useRef(null)
  const [chartAreaTop, setChartAreaTop] = useState(0)
  const [lassoSelection, setLassoSelection] = useState(null)
  const [plotDragMode, setPlotDragMode] = useState('zoom')

  const rowHeight = xAxisMode === 'tkin_time_wafer_id' || xAxisMode === 'eqc_tkin_time'
    ? SUBPLOT_H_WAFER
    : SUBPLOT_H
  const chartColumns = xAxisMode === 'eqc_tkin_time' ? EQC_TIME_NCOLS : NCOLS

  const chartPlan = useMemo(() => {
    if (data.length === 0) {
      return { keys: [], subtitle: '', sharedYRange: null, groupedData: new Map() }
    }

    if (xAxisMode === 'eqc_tkin_time') {
      const groupedData = new Map()
      data.forEach(row => {
        const key = row.stepSeq
        const rows = groupedData.get(key)
        if (rows) rows.push(row)
        else groupedData.set(key, [row])
      })
      const keys = [...groupedData.keys()].sort()
      return {
        keys,
        subtitle: `${new Set(data.map(d => d.eqc)).size} EQPCH · step_seq trellis`,
        sharedYRange: getSharedYRange(data),
        groupedData,
      }
    }

    if (trellisBy === 'eqc') {
      const groupedData = new Map()
      data.forEach(row => {
        const rows = groupedData.get(row.eqc)
        if (rows) rows.push(row)
        else groupedData.set(row.eqc, [row])
      })
      const baseKeys = [...groupedData.keys()].sort()
      const riskEqpchs = new Set(data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => d.eqc))
      const keys = highlightFirst
        ? sortHighlightFirst(baseKeys, eqc => riskEqpchs.has(eqc))
        : baseKeys
      const vals = data.map(d => d.binValue)
      const limits = data
        .map(d => d.propOver50 < 0.5 ? d.usl : d.lsl)
        .filter(v => v !== null && v !== undefined)
      const allY = [...vals, ...limits]
      const yMin = Math.min(...allY)
      const yMax = Math.max(...allY)
      const pad = Math.max((yMax - yMin) * 0.1, 1)
      return { keys, subtitle: `${keys.length} EQPCH · 공통 Y축`, sharedYRange: [yMin - pad, yMax + pad], groupedData }
    }

    if (trellisBy === 'bin') {
      const groupedData = new Map()
      data.forEach(row => {
        const rows = groupedData.get(row.binName)
        if (rows) rows.push(row)
        else groupedData.set(row.binName, [row])
      })
      const baseKeys = [...groupedData.keys()].sort()
      const riskBins = new Set(data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => d.binName))
      const keys = highlightFirst
        ? sortHighlightFirst(baseKeys, key => riskBins.has(key))
        : baseKeys
      return { keys, subtitle: `${keys.length} bin_name · 독립 Y축`, sharedYRange: null, groupedData }
    }

    const groupedData = new Map()
    data.forEach(row => {
      const key = `${row.stepSeq}|||${row.binName}`
      const rows = groupedData.get(key)
      if (rows) rows.push(row)
      else groupedData.set(key, [row])
    })
    const baseKeys = [...groupedData.keys()].sort()
    const riskStepBins = new Set(
      data.filter(d => d.displayStatus === 'High Risk Chamber').map(d => `${d.stepSeq}|||${d.binName}`),
    )
    const keys = highlightFirst
      ? sortHighlightFirst(baseKeys, key => riskStepBins.has(key))
      : baseKeys
    return { keys, subtitle: `${keys.length} step·bin · 독립 Y축`, sharedYRange: null, groupedData }
  }, [data, trellisBy, highlightFirst, xAxisMode])

  const keySignature = useMemo(() => chartPlan.keys.join('\u0001'), [chartPlan.keys])
  const totalRows = Math.ceil(chartPlan.keys.length / chartColumns)
  const totalHeight = Math.max(totalRows * rowHeight, 300)
  const viewportHeight = outerViewportHeight || DEFAULT_VIEWPORT_H
  const maxChartScrollTop = Math.max(totalHeight - viewportHeight, 0)
  const chartScrollTop = Math.min(Math.max(outerScrollTop - chartAreaTop, 0), maxChartScrollTop)
  const visibleRowStart = Math.max(Math.floor(chartScrollTop / rowHeight) - OVERSCAN_ROWS, 0)
  const visibleRowCount = Math.ceil(viewportHeight / rowHeight) + OVERSCAN_ROWS * 2
  const visibleRowEnd = Math.min(visibleRowStart + visibleRowCount, totalRows)
  const virtualOffset = visibleRowStart * rowHeight

  useLayoutEffect(() => {
    spacerRef.current?.style.setProperty('--tc-total-height', `${totalHeight}px`)
    // 스켈레톤 backdrop(빠른 스크롤 시 빈칸 채움)이 행 높이를 알 수 있게 spacer에도 설정
    spacerRef.current?.style.setProperty('--tc-row-height', `${rowHeight}px`)
    virtualWindowRef.current?.style.setProperty('--tc-virtual-offset', `${virtualOffset}px`)
    plotGridRef.current?.style.setProperty('--tc-chart-columns', String(chartColumns))
    plotGridRef.current?.style.setProperty('--tc-row-height', `${rowHeight}px`)
  }, [chartColumns, rowHeight, totalHeight, virtualOffset])

  const visibleKeys = useMemo(() => {
    const start = visibleRowStart * chartColumns
    const end = Math.min(visibleRowEnd * chartColumns, chartPlan.keys.length)
    return chartPlan.keys.slice(start, end)
  }, [chartPlan.keys, chartColumns, visibleRowStart, visibleRowEnd])

  const getGroupedRows = useCallback(
    (key) => chartPlan.groupedData.get(key) ?? [],
    [chartPlan.groupedData],
  )

  // 단일 key의 차트 객체를 빌드. 스크롤(visibleKeys)과 무관하고, 실제 입력
  // (데이터/축/trellis/공유Y/lasso)이 바뀔 때만 정체성이 바뀐다.
  const buildChartForKey = useCallback((key) => {
    const subData = getGroupedRows(key)
    if (xAxisMode === 'eqc_tkin_time') {
      return buildSingleEqcTimeChart(key, subData, lassoSelection)
    }
    if (trellisBy === 'eqc') {
      return buildSingleStandardChart(
        key, subData,
        `${key} / ${getStepPpidTitle(subData)}`,
        getLimitInfoFromRows(subData),
        chartPlan.sharedYRange,
        xAxisMode,
        lassoSelection,
      )
    }
    if (trellisBy === 'bin') {
      return buildSingleStandardChart(
        key, subData,
        `${key} / ${getUniqueText(subData.map(d => d.eqc))}`,
        getLimitInfoFromRows(subData),
        null,
        xAxisMode,
        lassoSelection,
      )
    }
    const [stepSeq, binName] = key.split('|||')
    return buildSingleStandardChart(
      key, subData,
      `${stepSeq} / ${getUniqueText(subData.map(d => d.ppid))} / ${binName}`,
      getLimitInfoFromRows(subData),
      null,
      xAxisMode,
      lassoSelection,
    )
  }, [getGroupedRows, xAxisMode, trellisBy, chartPlan.sharedYRange, lassoSelection])

  // key별 차트 객체 캐시: 스크롤로 visibleKeys가 바뀌어도 이미 만든 key는 같은 객체 참조를
  // 재사용한다. 그래야 FacetPlot의 plotData/plotLayout 참조가 유지되어 Plotly가 재그리기하지
  // 않는다(스크롤 시 보이는 차트를 매번 다시 그리던 것이 주 병목이었음).
  // buildChartForKey 정체성이 바뀌면(실제 입력 변경) 캐시를 비운다.
  const chartCacheRef = useRef({ build: null, map: new Map() })
  const visibleCharts = useMemo(() => {
    if (data.length === 0 || visibleKeys.length === 0) return []
    const cache = chartCacheRef.current
    if (cache.build !== buildChartForKey) {
      cache.build = buildChartForKey
      cache.map = new Map()
    }
    return visibleKeys.map(key => {
      let chart = cache.map.get(key)
      if (chart === undefined) {
        chart = buildChartForKey(key)
        cache.map.set(key, chart)
      }
      return chart
    })
  }, [data.length, visibleKeys, buildChartForKey])

  // ④ defer draw: 스크롤 중에는 새로 들어오는 subplot을 그리지 않고 placeholder만 두고,
  // 스크롤이 멈추면(≈140ms) 실제로 보이는 것만 그린다. 이미 그려진 subplot은 유지한다.
  // (subplot 행이 많아 viewport 밖에서 계속 새로 마운트되는 경우의 fling 히칭을 줄임)
  const [isScrolling, setIsScrolling] = useState(false)
  const prevScrollTopRef = useRef(outerScrollTop)
  useEffect(() => {
    if (prevScrollTopRef.current === outerScrollTop) return
    prevScrollTopRef.current = outerScrollTop
    setIsScrolling(true)
    const timer = setTimeout(() => setIsScrolling(false), 140)
    return () => clearTimeout(timer)
  }, [outerScrollTop])

  // 실제로 그릴(마운트할) key 집합. 멈춤 상태에선 보이는 것 전부, 스크롤 중엔
  // 화면 밖으로 나간 것만 제거하고 새 key는 추가하지 않는다(→ 새 것은 placeholder).
  const [drawnKeys, setDrawnKeys] = useState(() => new Set())
  useEffect(() => {
    if (!isScrolling) {
      setDrawnKeys(new Set(visibleKeys))
      return
    }
    setDrawnKeys(prev => {
      const visible = new Set(visibleKeys)
      let changed = false
      const next = new Set()
      prev.forEach(k => { if (visible.has(k)) next.add(k); else changed = true })
      return changed ? next : prev
    })
  }, [visibleKeys, isScrolling])

  const handleSelectedPoints = useCallback((points) => {
    if (lassoMode === 'off') return
    const keys = getSelectedPointKeys(points, lassoMode)
    if (keys.size === 0) return
    setLassoSelection(prev => {
      if (!prev || prev.mode !== lassoMode) return { mode: lassoMode, keys }
      const nextKeys = new Set(prev.keys)
      keys.forEach(key => {
        if (nextKeys.has(key)) nextKeys.delete(key)
        else nextKeys.add(key)
      })
      return nextKeys.size > 0 ? { mode: lassoMode, keys: nextKeys } : null
    })
  }, [lassoMode])

  const handleModebarPan = useCallback(() => {
    setPlotDragMode('pan')
    onLassoModeChange?.('off')
  }, [onLassoModeChange])

  const handleModebarLasso = useCallback((mode) => {
    setPlotDragMode('select')
    onLassoShapeChange?.('box')
    onLassoModeChange?.(mode)
  }, [onLassoModeChange, onLassoShapeChange])

  const handleModebarNeutral = useCallback(() => {
    setPlotDragMode('zoom')
    onLassoModeChange?.('off')
  }, [onLassoModeChange])

  useEffect(() => {
    setLassoSelection(null)
  }, [data, keySignature, chartPlan.keys.length])

  useEffect(() => {
    // 줌/팬으로 빠져나갈 때(lassoMode='off')는 하이라이트를 유지한다. 새 라쏘 모드로
    // 들어갈 때만 이전 선택을 초기화(새 선택 시작).
    if (lassoMode === 'off') return
    setLassoSelection(null)
  }, [lassoMode])

  useEffect(() => {
    if (lassoMode === 'off') {
      setPlotDragMode(prev => prev === 'lasso' || prev === 'select' ? 'zoom' : prev)
      return
    }
    setPlotDragMode(lassoShape === 'freeform' ? 'lasso' : 'select')
  }, [lassoMode, lassoShape])

  useLayoutEffect(() => {
    const chartArea = scrollerRef.current
    const scrollContainer = scrollContainerRef?.current
    if (!chartArea || !scrollContainer) return undefined

    const updateChartAreaTop = () => {
      const chartRect = chartArea.getBoundingClientRect()
      const scrollRect = scrollContainer.getBoundingClientRect()
      setChartAreaTop(scrollContainer.scrollTop + chartRect.top - scrollRect.top)
    }

    updateChartAreaTop()
    const observer = new ResizeObserver(updateChartAreaTop)
    observer.observe(chartArea)
    observer.observe(scrollContainer)
    window.addEventListener('resize', updateChartAreaTop)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateChartAreaTop)
    }
  }, [scrollContainerRef, data.length, keySignature, rowHeight, totalHeight])

  // ── captureAll: 전체 차트를 PNG 한 장으로 합성 다운로드 ──────────────────
  useImperativeHandle(ref, () => ({
    async captureAll(onProgress) {
      const { keys, groupedData, sharedYRange } = chartPlan
      if (!keys.length) return

      const CAPTURE_W = 900
      const captureH = rowHeight

      // 모든 키에 대해 차트 객체 빌드 (가상화 무시)
      const allCharts = keys.map(key => {
        const subData = groupedData.get(key) ?? []
        if (xAxisMode === 'eqc_tkin_time') {
          return buildSingleEqcTimeChart(key, subData, null)
        }
        if (trellisBy === 'eqc') {
          return buildSingleStandardChart(
            key, subData,
            `${key} / ${getStepPpidTitle(subData)}`,
            getLimitInfoFromRows(subData), sharedYRange, xAxisMode, null,
          )
        }
        if (trellisBy === 'bin') {
          return buildSingleStandardChart(
            key, subData,
            `${key} / ${getUniqueText(subData.map(d => d.eqc))}`,
            getLimitInfoFromRows(subData), null, xAxisMode, null,
          )
        }
        const [stepSeq, binName] = key.split('|||')
        return buildSingleStandardChart(
          key, subData,
          `${stepSeq} / ${getUniqueText(subData.map(d => d.ppid))} / ${binName}`,
          getLimitInfoFromRows(subData), null, xAxisMode, null,
        )
      })

      // 차트별 Plotly → PNG (순차 처리로 메모리 안전)
      const imgUrls = []
      for (let i = 0; i < allCharts.length; i++) {
        onProgress?.(i, allCharts.length)
        const chart = allCharts[i]
        const el = document.createElement('div')
        el.style.cssText = `position:fixed;left:-9999px;top:0;width:${CAPTURE_W}px;height:${captureH}px;visibility:hidden;`
        document.body.appendChild(el)
        try {
          await Plotly.newPlot(
            el,
            chart.plotData,
            { ...chart.plotLayout, width: CAPTURE_W, height: captureH },
            { staticPlot: true, displayModeBar: false },
          )
          imgUrls.push(await Plotly.toImage(el, { format: 'png', width: CAPTURE_W, height: captureH }))
        } catch {
          imgUrls.push(null)
        } finally {
          Plotly.purge(el)
          document.body.removeChild(el)
        }
      }
      onProgress?.(allCharts.length, allCharts.length)

      // 그리드로 합성
      const cols = chartColumns
      const rowCount = Math.ceil(allCharts.length / cols)
      const canvas = document.createElement('canvas')
      canvas.width = CAPTURE_W * cols
      canvas.height = captureH * rowCount
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      await Promise.all(imgUrls.map((url, i) => {
        if (!url) return Promise.resolve()
        return new Promise(resolve => {
          const img = new Image()
          img.onload = () => {
            ctx.drawImage(img, (i % cols) * CAPTURE_W, Math.floor(i / cols) * captureH)
            resolve()
          }
          img.onerror = resolve
          img.src = url
        })
      }))

      await new Promise(resolve => {
        canvas.toBlob(blob => {
          if (!blob) { resolve(); return }
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `l3_spider_charts_${new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')}.png`
          a.click()
          URL.revokeObjectURL(url)
          resolve()
        }, 'image/png')
      })
    },
  }), [chartPlan, xAxisMode, trellisBy, chartColumns, rowHeight])

  if (data.length === 0) {
    return (
      <div className="tc-empty">
        <div className="tc-empty-icon">📊</div>
        <div className="tc-empty-text">테이블에서 EQPCH 또는 bin_name을 클릭하세요</div>
      </div>
    )
  }

  const selectedCount = lassoSelection?.keys.size ?? 0

  return (
    <div className="tc-wrap">
      {selectedCount > 0 && (
        <button type="button" className="tc-clear-selection-float" onClick={() => setLassoSelection(null)}>
          선택 해제 ({selectedCount.toLocaleString()})
        </button>
      )}
      {visibleKeys.length === 0 && (
        <div className="tc-progress-placeholder">차트 준비 중…</div>
      )}
      <div
        ref={scrollerRef}
        className="tc-scroll"
      >
        <div ref={spacerRef} className="tc-spacer">
          <div ref={virtualWindowRef} className="tc-virtual-window">
            <div
              ref={plotGridRef}
              className="tc-plot-grid"
            >
              {visibleCharts.map(chart => {
                const draw = !isScrolling || drawnKeys.has(chart.key)
                return (
                  <div className="tc-plot-cell" key={chart.key}>
                    {draw ? (
                      <FacetPlot
                        chart={chart}
                        lassoMode={lassoMode}
                        lassoShape={lassoShape}
                        dragMode={plotDragMode}
                        onSelected={handleSelectedPoints}
                        onPanRequest={handleModebarPan}
                        onLassoRequest={handleModebarLasso}
                        onModebarNeutralRequest={handleModebarNeutral}
                      />
                    ) : (
                      <div className="tc-plot-defer" aria-hidden="true" />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
})

export default TrellisChart
