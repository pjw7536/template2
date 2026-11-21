import { PointerActivationConstraints } from "@dnd-kit/dom"
import { DragDropProvider, DragOverlay, PointerSensor, useDraggable, useDroppable } from "@dnd-kit/react"
import { GripVertical } from "lucide-react"
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { OrgPicker, pickOf } from "./OrgPicker.jsx"
import { Alert, Button, cx } from "./ui.jsx"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog.jsx"
import { moveMemberAffiliation } from "../lib/api.js"
import { attr, displayName } from "../lib/users.js"

const MoveContext = createContext(null)
// 키보드는 핸들 클릭과 같은 이동 폼에서 소속 선택·확인을 진행합니다.
const SENSORS = [PointerSensor.configure({
  activationConstraints: () => [new PointerActivationConstraints.Distance({ value: 6 })],
})]

/** 트리·상세의 드래그를 함께 처리하고 저장 전 이동할 소속을 확인합니다. */
export function MemberMoveProvider({ org, editing = false, onChanged, disabled, children }) {
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const saving = useRef(false)
  const returnFocus = useRef(null)
  const [overlayRoot, setOverlayRoot] = useState(document.fullscreenElement ?? document.body)
  useEffect(() => {
    const update = () => setOverlayRoot(document.fullscreenElement ?? document.body)
    document.addEventListener("fullscreenchange", update)
    return () => document.removeEventListener("fullscreenchange", update)
  }, [])

  const requestMove = useCallback((user, from, to = "") => {
    if (!editing || saving.current || from.name === to) return
    returnFocus.current = document.activeElement
    setError("")
    setPending({ user, from, pick: pickOf(org, to || from.name) })
  }, [editing, org])
  const blocked = disabled || busy || Boolean(pending)
  const moves = useMemo(() => ({ requestMove, editing, disabled: blocked }), [requestMove, editing, blocked])
  const close = () => {
    if (!saving.current) setPending(null)
  }
  const save = async () => {
    if (!editing || saving.current || !pending?.pick.sdwt || pending.pick.sdwt === pending.from.name) return
    saving.current = true
    setBusy(true)
    setError("")
    try {
      await moveMemberAffiliation(pending.user.id, pending.from.name, pending.pick.sdwt, org)
      setPending(null)
      onChanged(`${displayName(pending.user)}의 소속을 ${pending.from.name}에서 ${pending.pick.sdwt}(으)로 옮겼습니다.`)
    } catch (failure) {
      setError(`${failure.message} 일부 변경이 적용되었을 수 있어 구성원 목록을 다시 불러옵니다.`)
      onChanged()
    } finally {
      saving.current = false
      setBusy(false)
    }
  }
  const target = pending ? org.sdwts.get(pending.pick.sdwt) : null
  const mismatch = target && attr(pending.user, "deptname") && attr(pending.user, "deptname") !== target.team

  return (
    <MoveContext.Provider value={moves}>
      <DragDropProvider sensors={SENSORS} onDragEnd={(event) => {
        if (event.canceled) return
        const { source, target: drop } = event.operation
        if (source?.type === "affiliated-member" && drop?.data.sdwt) {
          requestMove(source.data.user, source.data.sdwt, drop.data.sdwt.name)
        }
      }}>
        {children}
        {editing ? createPortal(<DragOverlay dropAnimation={null}>
          {(source) => (
            <div className="flex items-center gap-2 rounded-md border border-primary bg-card px-3 py-2 text-sm shadow-md">
              <GripVertical className="size-4" aria-hidden="true" />
              <span>{displayName(source.data.user)}</span>
              <span className="text-xs text-muted-foreground">{source.data.sdwt.name}</span>
            </div>
          )}
        </DragOverlay>, overlayRoot) : null}
      </DragDropProvider>
      <Dialog open={Boolean(pending)} onOpenChange={(open) => { if (!open) close() }}>
        <DialogContent showCloseButton={!busy} onCloseAutoFocus={(event) => {
          event.preventDefault()
          const previous = returnFocus.current
          const fallback = document.querySelector('[aria-label="조직 트리"] button[aria-pressed="true"]')
          const focusTarget = previous?.isConnected && !previous.disabled ? previous : fallback
          focusTarget?.focus()
        }} onEscapeKeyDown={(event) => { if (busy) event.preventDefault() }}
          onPointerDownOutside={(event) => { if (busy) event.preventDefault() }}>
          <DialogHeader>
            <DialogTitle>구성원 소속 이동</DialogTitle>
            <DialogDescription>이동할 SDWT를 확인하세요. 이전 소속에서 빠지고 새 SDWT에 소속됩니다.</DialogDescription>
          </DialogHeader>
          {pending ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm font-semibold">{displayName(pending.user)}</p>
              <p className="text-sm text-muted-foreground">현재 소속: {pending.from.team} / {pending.from.line} / {pending.from.name}</p>
              <fieldset className="flex min-w-0 flex-col gap-2" disabled={busy}>
                <legend className="mb-2 text-sm font-medium">이동할 소속</legend>
                <OrgPicker org={org} value={pending.pick} disabled={busy}
                  onChange={(pick) => { setPending({ ...pending, pick }); setError("") }} />
              </fieldset>
              <p className="text-xs text-muted-foreground">SDWT·라인 속성과 소속으로 받는 권한이 바뀝니다. 직접 부여한 소속별 역할·앱 역할은 유지되며, 이전 SDWT 관리자 역할도 남습니다.</p>
              {mismatch ? <Alert tone="amber">사내 부서({attr(pending.user, "deptname")})와 이동할 팀({target.team})이 다릅니다. 사내 부서 속성은 변경하지 않습니다.</Alert> : null}
              {error ? <Alert>{error}</Alert> : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" disabled={busy} onClick={close}>취소</Button>
            <Button disabled={busy || !target || target.name === pending?.from.name} onClick={save}>{busy ? "이동 중…" : "소속 이동"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </MoveContext.Provider>
  )
}

/** 보기에서는 일반 목록만 마운트해 사람 수만큼 드래그 등록이 생기는 것을 막습니다. */
export function MovableMember(props) {
  const moves = useContext(MoveContext)
  if (!moves.editing) return <li className={props.className}>{props.children}</li>
  return <DraggableMember {...props} moves={moves} />
}

/** 편집에서만 드래그 hook과 이동 핸들을 등록합니다. */
function DraggableMember({ user, sdwt, location, disabled, className, children, moves }) {
  const blocked = disabled || moves.disabled
  const { ref, handleRef, isDragSource } = useDraggable({
    id: `${location}:${sdwt.id}:${user.id}`,
    type: "affiliated-member",
    data: { user, sdwt },
    disabled: blocked,
  })
  return (
    <li ref={ref} className={cx(className, isDragSource && "opacity-50")}>
      <Button ref={handleRef} variant="ghost" size="icon" className="size-6 shrink-0 touch-none cursor-grab active:cursor-grabbing"
        disabled={blocked} aria-label={`${displayName(user)} 소속 이동`} title="다른 SDWT로 드래그하거나 눌러 소속 이동"
        onClick={() => moves.requestMove(user, sdwt)}>
        <GripVertical aria-hidden="true" />
      </Button>
      {children}
    </li>
  )
}

/** 펼치지 않은 SDWT와 빈 SDWT에도 구성원을 놓을 수 있습니다. */
export function SdwtDropTarget({ sdwt, disabled, selected, expanded = selected, className, onSelect, children }) {
  const moves = useContext(MoveContext)
  const props = { sdwt, disabled, selected, expanded, className, onSelect, children }
  if (!moves.editing) return <SdwtNode {...props} />
  return <DroppableSdwt {...props} moves={moves} />
}

/** 편집에서만 SDWT를 드롭 대상으로 등록합니다. */
function DroppableSdwt({ sdwt, disabled, moves, ...props }) {
  const { ref, isDropTarget } = useDroppable({
    id: `sdwt:${sdwt.id}`,
    data: { sdwt },
    accept: (source) => source.type === "affiliated-member" && source.data.sdwt.name !== sdwt.name,
    disabled: disabled || moves.disabled,
  })
  return <SdwtNode {...props} nodeRef={ref} isDropTarget={isDropTarget} />
}

/** 보기와 편집에서 같은 노드 구조를 사용해 선택·펼침 동작을 유지합니다. */
function SdwtNode({ selected, expanded, className, onSelect, children, nodeRef, isDropTarget = false }) {
  return (
    <button ref={nodeRef} type="button" onClick={onSelect} aria-pressed={selected} aria-expanded={expanded}
      className={cx(
        "flex w-full items-center justify-between gap-2 rounded-md border bg-card px-3 py-1.5 text-left text-sm shadow-xs transition hover:bg-accent",
        selected && "border-primary ring-2 ring-primary/30",
        isDropTarget && "border-primary bg-accent ring-2 ring-primary",
        className,
      )}>
      {children}
      {isDropTarget ? <span className="shrink-0 text-xs font-medium">여기로 이동</span> : null}
    </button>
  )
}
