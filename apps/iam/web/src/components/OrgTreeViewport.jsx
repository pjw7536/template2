import { Hand, Maximize, Minimize, Minus, Plus, Scan } from "lucide-react"
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"

import { Alert, Button, cx } from "./ui.jsx"

const MAX_SCALE = 2
const ZOOM_FACTOR = 1.25

/** 변환에 영향받지 않는 트리 크기와 현재 표시 영역을 읽습니다. */
function readTreeSize(viewport, content) {
  const style = getComputedStyle(viewport)
  return {
    width: content.offsetWidth,
    height: content.offsetHeight,
    availableWidth: Math.max(0, viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 4),
    availableHeight: Math.max(0, viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - 4),
    paddingTop: parseFloat(style.paddingTop),
  }
}

/** 트리 원래 크기와 표시 영역을 관측해 자동 맞춤 또는 수동 배율로 표시합니다. */
export function OrgTreeViewport({ children, actions, fitKey, autoFit = false }) {
  const sectionRef = useRef(null)
  const viewportRef = useRef(null)
  const contentRef = useRef(null)
  const gestureRef = useRef(null)
  const suppressClick = useRef(false)
  const initialFit = useRef(false)
  const previousFitKey = useRef(fitKey)
  const [view, setView] = useState(null)
  const [handTool, setHandTool] = useState(true)
  const [panning, setPanning] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [fullscreenError, setFullscreenError] = useState("")
  const [size, setSize] = useState({ width: 0, height: 0, availableWidth: 0, availableHeight: 0 })

  useLayoutEffect(() => {
    const viewport = viewportRef.current
    const content = contentRef.current
    const measure = () => {
      const next = readTreeSize(viewport, content)
      setSize((current) => Object.keys(next).every((key) => next[key] === current[key]) ? current : next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(viewport)
    observer.observe(content)
    return () => observer.disconnect()
  }, [])

  const ready = size.width > 0 && size.height > 0 && size.availableWidth > 0 && size.availableHeight > 0
  const fitScale = ready ? Math.min(1, size.availableWidth / size.width, size.availableHeight / size.height) : 1
  const minScale = Math.min(0.1, fitScale)
  const scale = view?.scale ?? fitScale

  const fitView = useCallback(() => {
    const viewport = viewportRef.current
    const current = readTreeSize(viewport, contentRef.current)
    if (!current.width || !current.height || !current.availableWidth || !current.availableHeight) return
    const nextScale = Math.min(1, current.availableWidth / current.width, current.availableHeight / current.height)
    setView({
      scale: nextScale,
      x: (viewport.clientWidth - current.width * nextScale) / 2,
      y: current.paddingTop + 2,
    })
  }, [])

  // 최초 진입에만 맞추고, 노드 선택·상세 패널·구성원 갱신으로 배율을 되돌리지 않습니다.
  useLayoutEffect(() => {
    if (ready && !initialFit.current) {
      initialFit.current = true
      fitView()
    }
  }, [ready, fitView])

  // 일반 모드는 방향 전환 때만, Compact는 표시 영역·조직 크기가 달라질 때도 맞춥니다.
  useLayoutEffect(() => {
    const changed = previousFitKey.current !== fitKey
    previousFitKey.current = fitKey
    if (ready && (changed || autoFit)) fitView()
  }, [fitKey, autoFit, fitView, ready, size.width, size.height, size.availableWidth, size.availableHeight])

  const zoomTo = useCallback((value, point) => {
    const next = Math.min(MAX_SCALE, Math.max(minScale, value))
    if (!view || next === scale) return
    const viewport = viewportRef.current
    const outer = viewport.getBoundingClientRect()
    const viewX = point ? point.x - outer.left : viewport.clientWidth / 2
    const viewY = point ? point.y - outer.top : viewport.clientHeight / 2
    setView({
      scale: next,
      // 포인터 또는 표시 영역의 중심에 놓인 조직도 좌표를 고정합니다.
      x: viewX - (viewX - view.x) * next / scale,
      y: viewY - (viewY - view.y) * next / scale,
    })
  }, [view, minScale, scale])

  const finishGesture = useCallback(() => {
    const pan = gestureRef.current
    gestureRef.current = null
    setPanning(false)
    if (pan && viewportRef.current?.hasPointerCapture(pan.pointerId)) viewportRef.current.releasePointerCapture(pan.pointerId)
  }, [])

  useEffect(() => {
    const visibility = () => { if (document.hidden) finishGesture() }
    const fullscreenChanged = () => { setFullscreen(document.fullscreenElement === sectionRef.current); finishGesture() }
    window.addEventListener("blur", finishGesture)
    document.addEventListener("visibilitychange", visibility)
    document.addEventListener("fullscreenchange", fullscreenChanged)
    return () => {
      window.removeEventListener("blur", finishGesture)
      document.removeEventListener("visibilitychange", visibility)
      document.removeEventListener("fullscreenchange", fullscreenChanged)
    }
  }, [finishGesture])

  useEffect(() => {
    const viewport = viewportRef.current
    const wheel = (event) => {
      event.preventDefault()
      event.stopPropagation()
      if (!event.deltaY) return
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1)
      zoomTo(scale * Math.exp(-Math.max(-300, Math.min(300, pixels)) * 0.002), { x: event.clientX, y: event.clientY })
    }
    // 휠로 화면을 밀지 않고, 보조 키 없이 조직도만 확대·축소합니다.
    viewport.addEventListener("wheel", wheel, { passive: false })
    return () => viewport.removeEventListener("wheel", wheel)
  }, [scale, zoomTo])

  const startGesture = (event) => {
    // 노드 버튼과 구성원 이동 핸들은 원래 클릭·소속 이동 동작을 유지합니다.
    if (!handTool || !view || event.button !== 0 || event.pointerType === "touch" || event.target.closest("button, a[href], input, textarea, select, [contenteditable]")) {
      suppressClick.current = false
      return
    }
    event.preventDefault()
    event.stopPropagation()
    const viewport = viewportRef.current
    gestureRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, left: view.x, top: view.y }
    suppressClick.current = true
    setPanning(true)
    viewport.setPointerCapture(event.pointerId)
  }
  const moveGesture = (event) => {
    const gesture = gestureRef.current
    if (!gesture || event.pointerId !== gesture.pointerId) return
    event.preventDefault()
    event.stopPropagation()
    setView((current) => ({
      ...current,
      x: gesture.left + event.clientX - gesture.x,
      y: gesture.top + event.clientY - gesture.y,
    }))
  }
  const endGesture = (event) => {
    if (!gestureRef.current) return
    event.preventDefault()
    event.stopPropagation()
    finishGesture()
  }
  const toggleFullscreen = async () => {
    setFullscreenError("")
    try {
      // 조직도 영역만 브라우저 전체 화면으로 전환합니다.
      if (document.fullscreenElement) await document.exitFullscreen()
      else await sectionRef.current.requestFullscreen()
    } catch {
      setFullscreenError("전체 화면으로 전환할 수 없습니다. 브라우저의 전체 화면 허용 설정을 확인하세요.")
    }
  }

  return (
    <section ref={sectionRef} className={cx("flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border bg-muted/20", fullscreen && "rounded-none border-0 bg-background")} aria-label="조직 트리">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-card px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <span className="text-xs text-muted-foreground">빈 공간을 끌어 이동 · 휠/버튼 확대·축소</span>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="조직도 확대·축소">
          <Button variant={handTool ? "primary" : "outline"} size="sm" aria-pressed={handTool} onClick={() => { finishGesture(); setHandTool((value) => !value) }}>
            <Hand data-icon="inline-start" aria-hidden="true" />손 도구
          </Button>
          <Button variant="outline" size="icon-sm" aria-label="조직도 축소" title="축소" disabled={!ready || scale <= minScale} onClick={() => zoomTo(scale / ZOOM_FACTOR)}>
            <Minus aria-hidden="true" />
          </Button>
          <output className="min-w-12 text-center text-xs tabular-nums" aria-label="현재 배율" aria-live="polite">{Math.max(1, Math.round(scale * 100))}%</output>
          <Button variant="outline" size="icon-sm" aria-label="조직도 확대" title="확대" disabled={!ready || scale >= MAX_SCALE} onClick={() => zoomTo(scale * ZOOM_FACTOR)}>
            <Plus aria-hidden="true" />
          </Button>
          <Button variant="outline" size="sm" disabled={!ready} onClick={() => zoomTo(1)} aria-label="100% 배율로 보기">100%</Button>
          <Button variant="outline" size="sm" disabled={!ready} onClick={fitView}>
            <Scan data-icon="inline-start" aria-hidden="true" />화면 맞춤
          </Button>
          <Button variant="outline" size="sm" aria-pressed={fullscreen} onClick={toggleFullscreen}>
            {fullscreen ? <Minimize data-icon="inline-start" aria-hidden="true" /> : <Maximize data-icon="inline-start" aria-hidden="true" />}
            {fullscreen ? "전체 화면 종료" : "전체 보기"}
          </Button>
        </div>
      </div>
      {fullscreenError ? <Alert>{fullscreenError}</Alert> : null}
      <div ref={viewportRef} className={cx("relative min-h-0 min-w-0 flex-1 overflow-clip p-4", handTool && "cursor-grab select-none", panning && "cursor-grabbing")}
        aria-label="조직도 표시 영역" onPointerDownCapture={startGesture} onPointerMoveCapture={moveGesture} onPointerUpCapture={endGesture}
        onPointerCancelCapture={endGesture} onLostPointerCapture={finishGesture} onClickCapture={(event) => {
          if (suppressClick.current) {
            event.preventDefault()
            event.stopPropagation()
            suppressClick.current = false
          }
        }}>
        <div ref={contentRef} className="absolute left-0 top-0 w-max origin-top-left will-change-transform" style={{ transform: `translate(${view?.x ?? 0}px, ${view?.y ?? 0}px) scale(${scale})` }}>
          {children}
        </div>
      </div>
    </section>
  )
}
