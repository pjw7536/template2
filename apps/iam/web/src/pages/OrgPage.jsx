import { Check, Pencil, Plus, Upload, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { MemberMoveProvider, MovableMember, SdwtDropTarget } from "../components/OrgMemberMove.jsx"
import { OrgTreeViewport } from "../components/OrgTreeViewport.jsx"
import { Alert, Badge, Button, Card, FilePicker, Input, Select, cx } from "../components/ui.jsx"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog.jsx"
import { Label } from "../components/ui/label.jsx"
import {
  applyAffiliation, createSdwts, groupMembers, moveSdwt, saveJobTitle,
  searchUsers, userGroups,
} from "../lib/api.js"
import { readSdwtCsv, validGroupName } from "../lib/csv.js"
import { planAffiliation, planOrg } from "../lib/plan.js"
import { attr, displayName, JOB_TITLE_MAX_LENGTH, membersByJobTitle, summarizeMembers } from "../lib/users.js"

/**
 * 조직 탭: 팀 → 라인 → 파트(SDWT) 트리에서 선택한 조직의 현황과 실제 소속 구성원을 표시합니다.
 * 소속은 /org SDWT 그룹 가입이며, 직급은 grdName, 직책은 관리자가 입력하는 job_title입니다.
 * 자주 쓰지 않는 SDWT 추가·CSV 업로드는 모달로, 상세의 변경은 수정 버튼을 눌렀을 때만 보입니다.
 */

const TEAM_KEY = "iam.org.team"

function rememberedTeam() {
  try {
    return localStorage.getItem(TEAM_KEY) ?? ""
  } catch {
    return ""
  }
}

const byName = (a, b) => displayName(a.user).localeCompare(displayName(b.user))

/** 팀 아래 SDWT의 실제 소속 구성원을 속성과 함께 읽고 이름순으로 정렬합니다. */
function useTeamMembers(team) {
  const [state, setState] = useState({ loading: true, error: "", bySdwt: {} })
  const [version, setVersion] = useState(0)
  const key = team ? team.lines.map((line) => `${line.id}:${line.sdwts.map((sdwt) => sdwt.id).join(",")}`).join("|") : ""

  useEffect(() => {
    if (!team) return undefined
    let alive = true
    const sdwts = team.lines.flatMap((line) => line.sdwts)
    setState({ loading: true, error: "", bySdwt: {} })
    Promise.all(sdwts.map(async (sdwt) => {
      const members = await groupMembers(sdwt.id)
      return { affiliated: members.map((user) => ({ user })).sort(byName) }
    }))
      .then((perSdwt) => {
        if (!alive) return
        setState({
          loading: false, error: "",
          bySdwt: Object.fromEntries(sdwts.map((sdwt, index) => [sdwt.name, perSdwt[index]])),
        })
      })
      .catch((error) => alive && setState((current) => ({ ...current, loading: false, error: error.message })))
    return () => {
      alive = false
    }
    // 팀의 라인·SDWT 구성(key)이나 다시 읽기 요청(version)이 바뀌면 다시 읽습니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, version])

  const reload = useCallback(() => setVersion((value) => value + 1), [])
  const updateUser = useCallback((user) => setState((current) => ({
    ...current,
    bySdwt: Object.fromEntries(Object.entries(current.bySdwt).map(([name, people]) => [name, {
      affiliated: people.affiliated.map((entry) => entry.user.id === user.id ? { ...entry, user } : entry),
    }])),
  })), [])
  return { ...state, reload, updateUser }
}

export default function OrgPage({ orgRoot, org, orgUuid, reload }) {
  const [editing, setEditing] = useState(false)
  const [selectedTeam, setSelectedTeam] = useState(rememberedTeam)
  // 비어 있으면 전체 라인, 아니면 고른 라인 id만 표시합니다.
  const [lineFilter, setLineFilter] = useState(() => new Set())
  const [selectedSdwt, setSelectedSdwt] = useState("")
  const [expandedSdwts, setExpandedSdwts] = useState(() => new Set())
  const [treeLayout, setTreeLayout] = useState("vertical")
  const [compactTree, setCompactTree] = useState(false)
  const [selectedLine, setSelectedLine] = useState("")
  const [selectedPerson, setSelectedPerson] = useState(null)
  const personTrigger = useRef(null)
  const [dialog, setDialog] = useState("")
  const [message, setMessage] = useState(null)
  // 고른 팀이 없거나 사라졌으면 첫 팀을 보여 줍니다.
  const team = org.teams.find((item) => item.name === selectedTeam) ?? org.teams[0]
  const members = useTeamMembers(team)
  const lines = team ? team.lines.filter((line) => !lineFilter.size || lineFilter.has(line.id)) : []
  const sdwt = selectedSdwt ? org.sdwts.get(selectedSdwt) : null
  const shownSdwt = sdwt && sdwt.team === team?.name ? sdwt : null
  const shownLine = team?.lines.find((line) => line.id === selectedLine)

  const selectSdwt = (name) => {
    setSelectedLine("")
    const closing = selectedSdwt === name && expandedSdwts.has(name)
    setSelectedSdwt(closing ? "" : name)
    setExpandedSdwts((current) => {
      const next = new Set(current)
      if (closing) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const selectLine = (id) => {
    setSelectedSdwt("")
    setSelectedLine((current) => current === id ? "" : id)
  }

  const showPerson = (user, affiliation, event) => {
    personTrigger.current = event.currentTarget
    setSelectedPerson({ user, sdwt: affiliation })
  }

  const chooseTeam = (name) => {
    setEditing(false)
    setSelectedTeam(name)
    setLineFilter(new Set())
    setSelectedSdwt("")
    setSelectedLine("")
    setExpandedSdwts(new Set())
    try {
      localStorage.setItem(TEAM_KEY, name)
    } catch {
      // 저장이 막혀도 화면 동작에는 영향이 없습니다.
    }
  }

  const afterChange = async (text) => {
    if (text) setMessage({ tone: "green", text })
    await reload()
    members.reload()
  }
  const editAction = (
    <Button size="sm" variant={editing ? "primary" : "outline"} aria-label="조직 편집" aria-pressed={editing}
      onClick={() => setEditing((current) => !current)}>
      {editing ? <Check data-icon="inline-start" /> : <Pencil data-icon="inline-start" />}
      {editing ? "편집 종료" : "편집"}
    </Button>
  )

  return (
    <MemberMoveProvider org={org} editing={editing} disabled={members.loading || Boolean(members.error)} onChanged={(text) => {
      if (text) setMessage({ tone: "green", text })
      members.reload()
    }}>
      {/* 조직도 카드는 남은 화면 높이를 채우고, 스크롤은 카드 안의 트리·상세에서만 생깁니다. */}
      <div className="flex h-full min-h-0 flex-col">
        <Card
          className="flex min-h-0 flex-1 flex-col"
          contentClassName="flex min-h-0 flex-1 flex-col"
          title="조직도"
          description="라인·파트나 이름을 눌러 상세정보를 봅니다. 편집을 켜면 이동 핸들로 구성원의 소속을 옮길 수 있습니다."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Select aria-label="팀" value={team?.name ?? ""} onChange={(event) => chooseTeam(event.target.value)}>
                {org.teams.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
              </Select>
              {!team ? editAction : null}
              {editing ? <>
                <Button variant="outline" onClick={() => setDialog("add")}><Plus className="size-4" />SDWT 추가</Button>
                <Button variant="outline" onClick={() => setDialog("csv")}><Upload className="size-4" />CSV 업로드</Button>
              </> : null}
            </div>
          }
        >
          {!team ? <p className="text-sm text-muted-foreground">아직 팀이 없습니다. 편집을 켜고 SDWT 추가로 팀·라인·SDWT를 만드세요.</p> : (
            <div className="flex min-h-0 flex-1 flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2" role="group" aria-label="라인">
                {[{ id: "", name: "" }, ...team.lines].map((line) => {
                  const selected = line.id ? lineFilter.has(line.id) : !lineFilter.size
                  return (
                    <button key={line.id || "all"} type="button" aria-pressed={selected} onClick={() => {
                      // 라인 버튼은 여러 개를 켜고 끌 수 있고, `전체`는 선택을 비웁니다.
                      setLineFilter((current) => {
                        if (!line.id) return new Set()
                        const next = new Set(current)
                        if (next.has(line.id)) next.delete(line.id)
                        else next.add(line.id)
                        return next
                      })
                      setSelectedLine("")
                      setSelectedSdwt("")
                    }}
                      className={cx(
                        "inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors",
                        selected ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-accent",
                      )}>
                      {line.name || "전체"}
                      <span className={cx("text-xs", selected ? "text-primary-foreground/80" : "text-muted-foreground")}>
                        {line.name ? line.sdwts.length : team.lines.reduce((sum, item) => sum + item.sdwts.length, 0)}
                      </span>
                    </button>
                  )
                })}
              </div>
              <div className={cx("relative grid min-h-0 flex-1 gap-4", !compactTree && "grid-cols-[minmax(0,1fr)_26rem]")}>
                {message || members.error ? (
                  <div className="absolute bottom-3 left-3 z-10 max-w-md rounded-md bg-background">
                    {members.error ? <Alert>{members.error}</Alert> : <Alert tone={message.tone}>{message.text}</Alert>}
                  </div>
                ) : null}
                <OrgTree team={team} lines={lines} members={members} selected={shownSdwt?.name}
                  editAction={editAction}
                  expanded={expandedSdwts} layout={treeLayout} onLayoutChange={setTreeLayout}
                  compact={compactTree} onCompactChange={setCompactTree}
                  onExpandAll={(open) => setExpandedSdwts((current) => {
                    const next = new Set(current)
                    for (const line of lines) for (const sdwt of line.sdwts) {
                      if (open) next.add(sdwt.name)
                      else next.delete(sdwt.name)
                    }
                    return next
                  })}
                  selectedLine={shownLine?.id} onSelectLine={selectLine}
                  onSelect={selectSdwt}
                  onSelectPerson={showPerson} />
                {!compactTree && shownLine ? (
                  <LineDetail line={shownLine} members={members} onSelectPerson={showPerson} onSelectSdwt={(name) => {
                    selectSdwt(name)
                    // 목록이 파트 상세로 바뀌어도 키보드 초점을 새 상세에 유지합니다.
                    requestAnimationFrame(() => document.getElementById("org-part-details")?.focus())
                  }}
                    onClose={() => setSelectedLine("")} />
                ) : null}
                {!compactTree && shownSdwt ? (
                  <SdwtDetail
                    key={shownSdwt.id}
                    sdwt={shownSdwt}
                    team={team}
                    orgUuid={orgUuid}
                    org={org}
                    people={members.bySdwt[shownSdwt.name] ?? { affiliated: [] }}
                    loading={members.loading}
                    error={members.error}
                    editing={editing}
                    onSelectPerson={showPerson}
                    onClose={() => setSelectedSdwt("")}
                    onChanged={afterChange}
                    onMembersChanged={members.reload}
                  />
                ) : null}
                {!compactTree && !shownSdwt && !shownLine ? (
                  <section className="rounded-md border bg-card p-4" aria-label="조직 상세">
                    <p className="text-sm text-muted-foreground">라인·SDWT를 선택하면 상세정보를 표시합니다.</p>
                  </section>
                ) : null}
              </div>
            </div>
          )}
        </Card>

        <PersonDetails person={selectedPerson} editing={editing} onClose={() => setSelectedPerson(null)} triggerRef={personTrigger} onRefresh={members.reload}
          onSaved={(user) => {
            members.updateUser(user)
            setSelectedPerson((current) => current ? { ...current, user } : current)
          }} />

        <CreateDialog
          open={dialog === "add"}
          onOpenChange={(open) => setDialog(open ? "add" : "")}
          title="SDWT 추가"
          description="없는 팀·라인은 함께 만들고, 새 SDWT의 소속별 역할(조회·일반·관리자)도 준비합니다. 같은 라인 이름이 다른 팀에 있어도 됩니다."
          orgRoot={orgRoot}
          orgUuid={orgUuid}
          onDone={afterChange}
        >
          {(preview) => <AddForm org={org} team={team} onPreview={preview} />}
        </CreateDialog>
        <CreateDialog
          open={dialog === "csv"}
          onOpenChange={(open) => setDialog(open ? "csv" : "")}
          title="목록 CSV 업로드"
          description="헤더 user_sdwt_prod,line_id,department(팀 = 사내 부서명). 없는 팀·라인·SDWT만 만들고 기존 것은 바꾸지 않습니다."
          orgRoot={orgRoot}
          orgUuid={orgUuid}
          onDone={afterChange}
        >
          {(preview) => (
            <FilePicker label="CSV 파일 선택" onText={(text, name) => {
              const { items, errors } = readSdwtCsv(text)
              preview(name, items, errors)
            }} />
          )}
        </CreateDialog>
      </div>
    </MemberMoveProvider>
  )
}

/**
 * 조직 트리: 팀 아래로 라인·SDWT가 좌우로 펼쳐지는 가로형(layout "vertical")과
 * 팀 → 라인 → SDWT를 왼쪽부터 위아래로 쌓는 세로형(layout "horizontal")을 제공합니다.
 * 라인·SDWT 노드를 누르면 해당 조직의 상세가 열립니다.
 */
function OrgTree({ team, lines, members, editAction, selected, expanded, layout, compact, onLayoutChange, onCompactChange, onExpandAll, selectedLine, onSelectLine, onSelect, onSelectPerson }) {
  const peopleOf = (sdwt) => members.bySdwt[sdwt.name]?.affiliated ?? []
  const listedPeopleOf = (sdwt) => peopleOf(sdwt).filter(({ user }) => !["PL", "파트장"].includes(attr(user, "job_title").trim()))
  const count = (sdwt) => summarizeMembers(peopleOf(sdwt)).total
  const lineCount = (line) => summarizeMembers(line.sdwts.flatMap(peopleOf)).total
  const total = summarizeMembers(team.lines.flatMap((line) => line.sdwts.flatMap(peopleOf))).total
  const showCount = (number) => members.loading ? "…" : members.error ? "확인 불가" : `${number}명`
  const horizontal = layout === "horizontal"
  const visibleSdwts = lines.flatMap((line) => line.sdwts)
  const allExpanded = visibleSdwts.length > 0 && visibleSdwts.every((sdwt) => expanded.has(sdwt.name))
  const anyExpanded = visibleSdwts.some((sdwt) => expanded.has(sdwt.name))

  return (
    <OrgTreeViewport key={team.id} fitKey={`${layout}:${compact}`} autoFit={compact} actions={
      <>
        {editAction}
        <div className="flex items-center gap-1" role="group" aria-label="조직도 방향">
          <Button size="sm" variant={horizontal ? "outline" : "primary"} aria-pressed={!horizontal} onClick={() => onLayoutChange("vertical")}>가로형</Button>
          <Button size="sm" variant={horizontal ? "primary" : "outline"} aria-pressed={horizontal} onClick={() => onLayoutChange("horizontal")}>세로형</Button>
        </div>
        <Button size="sm" variant={compact ? "primary" : "outline"} aria-pressed={compact} onClick={() => onCompactChange(!compact)}>Compact</Button>
        {!compact ? <div className="flex items-center gap-1" role="group" aria-label="인원 펼침">
          <Button size="sm" variant="outline" disabled={members.loading || Boolean(members.error) || !visibleSdwts.length || allExpanded} onClick={() => onExpandAll(true)}>인원 모두 펼치기</Button>
          <Button size="sm" variant="outline" disabled={!anyExpanded} onClick={() => onExpandAll(false)}>모두 접기</Button>
        </div> : null}
      </>
    }>
      <div className={cx("flex w-max items-center", !horizontal && "flex-col")}>
        <div className="w-36 shrink-0 rounded-md border-2 border-primary bg-background px-3 py-2 text-center shadow-xs">
          <p className="text-sm font-semibold">{team.name}</p>
          <p className="text-xs text-muted-foreground">소속 구성원 {showCount(total)}</p>
        </div>
        {lines.length ? (
          <>
            <div className={horizontal ? "w-4 shrink-0 border-t" : compact ? "h-8 border-l" : "h-10 border-l"} aria-hidden="true" />
            <ul className={cx("grid gap-6", horizontal ? "auto-rows-fr grid-flow-row" : "auto-cols-fr grid-flow-col")}>
              {lines.map((line) => (
                <li
                  key={line.id}
                  className={cx(
                    "relative flex items-center",
                    horizontal ? "pl-4 before:absolute before:top-1/2 before:left-0 before:w-4 before:border-t"
                      : compact ? "flex-col pt-8 before:absolute before:top-0 before:left-1/2 before:h-8 before:border-l"
                        : "flex-col pt-10 before:absolute before:top-0 before:left-1/2 before:h-10 before:border-l",
                    lines.length > 1 && (horizontal
                      ? "after:absolute after:left-0 after:-top-3 after:-bottom-3 after:border-l first:after:top-1/2 last:after:bottom-1/2"
                      : "after:absolute after:top-0 after:-right-3 after:-left-3 after:border-t first:after:left-1/2 last:after:right-1/2"),
                  )}
                >
                  <div
                    className={cx(
                      "w-36 shrink-0 rounded-md border bg-background text-center shadow-xs",
                      selectedLine === line.id && "border-primary ring-2 ring-primary/30",
                    )}>
                    <button type="button" aria-pressed={selectedLine === line.id} onClick={() => onSelectLine(line.id)}
                      className={cx("w-full px-3 py-2 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", compact ? "rounded-md" : "rounded-t-md")}>
                      <p className="text-sm font-semibold">{line.name}</p>
                      <p className="text-xs text-muted-foreground">
                        파트 {line.sdwts.length} · {showCount(lineCount(line))}
                      </p>
                    </button>
                    {!compact ? <NodeRepresentatives name={line.name} title="PL" loading={members.loading} error={members.error}
                      people={line.sdwts.flatMap((sdwt) => peopleOf(sdwt).map((entry) => ({ ...entry, sdwt })))} onSelectPerson={onSelectPerson} /> : null}
                  </div>
                  {line.sdwts.length ? (
                    <>
                      <div className={horizontal ? "w-4 shrink-0 border-t" : compact ? "h-8 border-l" : "h-10 border-l"} aria-hidden="true" />
                      <ul className={compact
                        ? horizontal ? "flex items-center gap-3" : "relative flex flex-col gap-3 border-l pt-3 pl-4 before:absolute before:top-0 before:left-0 before:w-1/2 before:border-t"
                        : horizontal ? "grid auto-rows-fr gap-5" : "flex items-start gap-3"}>
                        {line.sdwts.map((sdwt) => (
                          <li key={sdwt.id} className={cx(
                            "relative shrink-0",
                            compact
                              ? horizontal ? "w-36 before:absolute before:top-1/2 before:-left-3 before:w-3 before:border-t first:before:hidden"
                                : "w-36 before:absolute before:top-1/2 before:-left-4 before:w-4 before:border-t"
                              : horizontal ? "flex items-center pl-4 before:absolute before:top-1/2 before:left-0 before:w-4 before:border-t"
                                : "w-36 pt-10 before:absolute before:top-0 before:left-1/2 before:h-10 before:border-l",
                            !compact && line.sdwts.length > 1 && (horizontal
                              ? "after:absolute after:left-0 after:-top-2.5 after:-bottom-2.5 after:border-l first:after:top-1/2 last:after:bottom-1/2"
                              : "after:absolute after:top-0 after:-right-1.5 after:-left-1.5 after:border-t first:after:left-1/2 last:after:right-1/2"),
                          )}>
                            <div className={cx("rounded-md border bg-card", horizontal && "w-36 shrink-0")}>
                              <SdwtDropTarget sdwt={sdwt} disabled={members.loading || Boolean(members.error)}
                                className={cx("border-0 shadow-none", !compact && "rounded-b-none")} expanded={!compact && expanded.has(sdwt.name)}
                                selected={selected === sdwt.name} onSelect={() => onSelect(sdwt.name)}>
                                <span className="truncate font-medium">{sdwt.name}</span>
                                <span className="shrink-0 text-xs text-muted-foreground">{showCount(count(sdwt))}</span>
                              </SdwtDropTarget>
                              {!compact ? <NodeRepresentatives name={sdwt.name} title="파트장" loading={members.loading} error={members.error}
                                people={peopleOf(sdwt).map((entry) => ({ ...entry, sdwt }))} onSelectPerson={onSelectPerson} /> : null}
                            </div>
                            {!compact && expanded.has(sdwt.name) ? (
                              <>
                                {horizontal ? <div className="w-4 shrink-0 border-t" aria-hidden="true" /> : null}
                                <ul className={cx("border-l", horizontal
                                  ? "grid w-max shrink-0 grid-flow-col auto-cols-max items-center gap-x-3 gap-y-2 pl-3"
                                  : "ml-2 mt-1", horizontal && (listedPeopleOf(sdwt).length > 1 ? "grid-rows-2" : "grid-rows-1"))} aria-label={`${sdwt.name} 구성원`}>
                                  {listedPeopleOf(sdwt).map(({ user }) => (
                                    <MovableMember key={user.id} user={user} sdwt={sdwt} location="tree"
                                      disabled={members.loading || Boolean(members.error)}
                                      className={cx(
                                        "relative flex items-center gap-1 text-xs",
                                        horizontal
                                          ? "w-36 shrink-0 rounded-md border bg-card px-2 py-1 before:absolute before:top-1/2 before:-left-3 before:w-3 before:border-t"
                                          : "py-0.5 pl-3 before:absolute before:top-1/2 before:left-0 before:w-2 before:border-t",
                                      )}>
                                      <button type="button" aria-haspopup="dialog"
                                        className="min-w-0 flex-1 truncate rounded-sm text-left hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        title={attr(user, "loginid") || user.username}
                                        onClick={(event) => onSelectPerson(user, sdwt, event)}>{displayName(user)}</button>
                                      <span className="max-w-14 shrink-0 truncate" title={attr(user, "job_title")}><Badge>{attr(user, "job_title") || "-"}</Badge></span>
                                    </MovableMember>
                                  ))}
                                  {members.loading || members.error || !listedPeopleOf(sdwt).length ? (
                                    <li className={cx("text-xs text-muted-foreground", horizontal
                                      ? "w-36 shrink-0 rounded-md border bg-card px-2 py-1"
                                      : "relative py-0.5 pl-3 before:absolute before:top-1/2 before:left-0 before:w-2 before:border-t")}>
                                      {members.loading ? "불러오는 중…" : members.error ? "인원 확인 불가" : peopleOf(sdwt).length ? "추가 구성원 없음" : "구성원 없음"}
                                    </li>
                                  ) : null}
                                </ul>
                              </>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : <p className="mt-2 text-xs text-muted-foreground">SDWT 없음</p>}
                </li>
              ))}
            </ul>
          </>
        ) : <p className="mt-3 text-sm text-muted-foreground">라인이 없습니다.</p>}
      </div>
    </OrgTreeViewport>
  )
}

/** 조직 노드 아래에 해당 범위의 대표를 표시하고 이름에서 사용자 상세를 엽니다. */
function NodeRepresentatives({ name, title, people, loading, error, onSelectPerson }) {
  const holders = membersByJobTitle(people).find((group) => group.title === title)?.people ?? []
  return (
    <div className="flex flex-col gap-1 border-t px-2 py-1.5 text-left text-xs" role="group" aria-label={`${name} ${title}`}>
      <span className="font-medium text-muted-foreground">{title}</span>
      {loading ? <span className="text-muted-foreground">불러오는 중…</span>
        : error ? <span className="text-muted-foreground">확인 불가</span>
        : holders.length ? holders.map(({ user, sdwt }) => (
          <button key={user.id} type="button" aria-haspopup="dialog" title={`${displayName(user)} · ${attr(user, "loginid") || user.username}`}
            className="w-full truncate rounded-sm text-left hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={(event) => onSelectPerson(user, sdwt, event)}>{displayName(user)}</button>
        )) : <span className="text-muted-foreground">미등록</span>}
    </div>
  )
}

/** 라인과 파트에서 같은 기준으로 전체 인원·직급별 인원을 표시합니다. */
function MemberSummary({ people, loading, error }) {
  if (loading) return <p role="status" className="text-sm text-muted-foreground">인원 정보를 불러오는 중…</p>
  if (error) return <p className="text-sm text-muted-foreground">인원 정보를 확인할 수 없습니다.</p>
  const summary = summarizeMembers(people)

  return (
    <section className="flex flex-col gap-3" aria-label="인원 현황">
      <dl className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2 text-sm">
        <dt>전체 인원</dt>
        <dd className="font-semibold tabular-nums">{summary.total}명</dd>
      </dl>
      <div>
        <h4 className="mb-1 text-sm font-semibold">직급별 인원</h4>
        {summary.grades.length ? (
          <dl className="divide-y rounded-md border text-sm">
            {summary.grades.map(({ name, count }) => (
              <div key={name} className="flex items-center justify-between gap-2 px-3 py-1.5">
                <dt>{name}</dt>
                <dd className="tabular-nums">{count}명</dd>
              </div>
            ))}
          </dl>
        ) : <p className="text-xs text-muted-foreground">소속 구성원 없음</p>}
      </div>
    </section>
  )
}

/** 입력한 직책을 기준으로 담당자를 표시하며 이름을 누르면 같은 사용자 상세를 엽니다. */
function JobTitleSummary({ people, scope, loading, error, onSelectPerson }) {
  if (loading || error) return null
  const groups = membersByJobTitle(people).filter(({ title }) => scope === "line" || title !== "PL")
  return (
    <section className="flex flex-col gap-2" aria-label="직책별 담당자">
      <h4 className="text-sm font-semibold">직책별 담당자</h4>
      <dl className="divide-y rounded-md border text-sm">
        {groups.map(({ title, people: holders }) => (
          <div key={title} className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 px-3 py-2">
            <dt className="break-all font-medium">{title}</dt>
            <dd className="flex min-w-0 flex-wrap gap-x-3 gap-y-1">
              {holders.length ? holders.map(({ user, sdwt }) => (
                <button key={user.id} type="button" aria-haspopup="dialog" title={user.username}
                  className="truncate rounded-sm text-left hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={(event) => onSelectPerson(user, sdwt, event)}>
                  {displayName(user)}{scope === "line" && title === "파트장" ? ` (${sdwt.name})` : ""}
                </button>
              )) : <span className="text-muted-foreground">미등록</span>}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

/** 라인의 분임조(파트·SDWT)와 실제 소속 구성원 집계를 표시합니다. */
function LineDetail({ line, members, onSelectPerson, onSelectSdwt, onClose }) {
  const people = line.sdwts.flatMap((sdwt) => (members.bySdwt[sdwt.name]?.affiliated ?? []).map((entry) => ({ ...entry, sdwt })))

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border bg-card" aria-label={`${line.name} 라인 정보`}>
      <header className="flex items-start gap-2 border-b px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted-foreground">라인 정보</p>
          <h3 className="truncate text-base font-semibold">{line.name}</h3>
          <p className="mt-1 text-xs text-muted-foreground">소속 팀: {line.team}</p>
        </div>
        <Button variant="ghost" className="size-8 px-0" onClick={onClose} aria-label="상세 닫기"><X className="size-4" /></Button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-3">
        <MemberSummary people={people} loading={members.loading} error={members.error} />
        <JobTitleSummary people={people} scope="line" loading={members.loading} error={members.error} onSelectPerson={onSelectPerson} />
        <section>
          <h4 className="mb-1 text-sm font-semibold">분임조(파트·SDWT) {line.sdwts.length}개</h4>
          <ul className="divide-y rounded-md border">
            {line.sdwts.map((sdwt) => (
              <li key={sdwt.id}>
                <button type="button" className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                  onClick={() => onSelectSdwt(sdwt.name)}>
                  <span className="min-w-0 truncate">{sdwt.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {members.loading ? "불러오는 중…" : members.error ? "확인 불가" : `${summarizeMembers(members.bySdwt[sdwt.name]?.affiliated ?? []).total}명`}
                  </span>
                </button>
              </li>
            ))}
            {!line.sdwts.length ? <li className="px-3 py-2 text-sm text-muted-foreground">하위 파트 없음</li> : null}
          </ul>
        </section>
      </div>
    </section>
  )
}

/** 파트의 인원 현황·구성원을 표시하고, 조직 편집 상태에서 소속·라인 위치를 바꿉니다. */
function SdwtDetail({ sdwt, team, org, orgUuid, people, loading, error, editing, onSelectPerson, onClose, onChanged, onMembersChanged }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const existing = people.affiliated.map(({ user }) => user.id)

  const run = async (action, text, after = onMembersChanged) => {
    setBusy(true)
    setMessage(null)
    try {
      await action()
      setMessage({ tone: "green", text })
      await after()
    } catch (error) {
      setMessage({ tone: "red", text: error.message })
    } finally {
      setBusy(false)
    }
  }

  /** 소속을 이 SDWT로 바꾸거나(newSdwt = sdwt) 소속을 해제합니다(newSdwt = ""). */
  const changeAffiliation = (user, newSdwt) => run(async () => {
    const groups = await userGroups(user.id)
    const plan = planAffiliation({ attributes: user.attributes, groupPaths: groups.map((group) => group.path), newSdwt, org })
    if (plan.error) throw new Error(plan.error)
    await applyAffiliation(user, groups, plan)
  }, newSdwt ? `${displayName(user)}의 소속을 ${sdwt.name}(으)로 바꿨습니다.` : `${displayName(user)}의 소속을 해제했습니다.`)

  const row = (entry) => (
    <MovableMember key={entry.user.id} user={entry.user} sdwt={sdwt} location="detail"
      disabled={busy || loading} className="flex items-center gap-2 px-3 py-1.5 text-sm">
      <button type="button" aria-haspopup="dialog"
        className="min-w-0 flex-1 truncate rounded-sm text-left hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={entry.user.username} onClick={(event) => onSelectPerson(entry.user, sdwt, event)}>
        {displayName(entry.user)}
        <span className="ml-1 text-xs text-muted-foreground">{attr(entry.user, "loginid") || entry.user.username}</span>
      </button>
      <span className="w-12 shrink-0 truncate text-xs text-muted-foreground" title={attr(entry.user, "grdName")}>{attr(entry.user, "grdName") || "-"}</span>
      <span className="w-14 shrink-0 truncate text-xs" title={attr(entry.user, "job_title")}>{attr(entry.user, "job_title") || "-"}</span>
      {editing ? (
        <Button variant="danger" className="h-7 px-2 text-xs" disabled={busy}
          onClick={() => {
            if (window.confirm(`${displayName(entry.user)}의 소속(${sdwt.name})을 해제할까요? 직접 받은 역할은 남습니다.`)) changeAffiliation(entry.user, "")
          }}>
          소속 해제
        </Button>
      ) : null}
    </MovableMember>
  )

  return (
    <section id="org-part-details" tabIndex={-1} className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-md border bg-card" aria-label={`${sdwt.name} 상세`}>
      <header className="flex items-start gap-2 border-b px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted-foreground">파트 정보</p>
          <h3 className="truncate text-base font-semibold">{sdwt.name}</h3>
          <dl className="mt-1 grid gap-0.5 text-xs text-muted-foreground">
            <div><dt className="inline">팀 / 라인 </dt><dd className="inline font-medium text-foreground">{sdwt.team} / {sdwt.line}</dd></div>
          </dl>
        </div>
        <Button variant="ghost" className="size-8 px-0" onClick={onClose} aria-label="상세 닫기"><X className="size-4" /></Button>
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-auto p-3">
        {message ? <Alert tone={message.tone}>{message.text}</Alert> : null}
        <MemberSummary people={people.affiliated} loading={loading} error={error} />
        <JobTitleSummary people={people.affiliated.map((entry) => ({ ...entry, sdwt }))} scope="part" loading={loading} error={error} onSelectPerson={onSelectPerson} />
        <div>
          <h4 className="mb-1 text-sm font-semibold">소속 구성원 {loading || error ? "" : `${people.affiliated.length}명`}</h4>
          <p className="mb-1.5 text-xs text-muted-foreground">직급과 직책을 구분해 표시합니다. 편집을 켠 뒤 이름을 누르면 직책을 수정할 수 있습니다.</p>
          <div className="flex items-center gap-2 px-3 py-1 text-xs text-muted-foreground" aria-hidden="true">
            <span className="flex-1">구성원</span><span className="w-12">직급</span><span className="w-14">직책</span>
            {editing ? <span className="w-16" /> : null}
          </div>
          <ul className="divide-y rounded-md border">
            {people.affiliated.map(row)}
            {!loading && !error && people.affiliated.length === 0 ? <li className="px-3 py-2 text-xs text-muted-foreground">소속 구성원 없음</li> : null}
          </ul>
        </div>
        {editing ? (
          <AddPerson busy={busy} existing={existing} onAdd={(user) => changeAffiliation(user, sdwt.name)} />
        ) : null}
        {editing ? (
          <MoveLine sdwt={sdwt} team={team} busy={busy}
            onMove={(line) => run(() => moveSdwt(orgUuid, sdwt, line),
              `${sdwt.name}을(를) ${line.name} 라인으로 옮겼습니다. 라인 전체 역할과 소속 구성원의 라인 속성도 바꿨습니다.`, () => onChanged())} />
        ) : null}
      </div>
    </section>
  )
}

/** 조직 구성원의 인사 정보·소속을 조회하고 직책만 수정합니다. */
function PersonDetails({ person, editing, onClose, onSaved, onRefresh, triggerRef }) {
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const saving = useRef(false)
  const user = person?.user
  const sdwt = person?.sdwt
  const jobTitle = draft ?? attr(user, "job_title")
  const changed = jobTitle.trim() !== attr(user, "job_title").trim()

  const close = () => {
    if (saving.current) return
    setDraft(null)
    setMessage(null)
    onClose()
  }
  const save = async () => {
    if (!editing || saving.current || !user || !changed) return
    saving.current = true
    setBusy(true)
    setMessage(null)
    try {
      const saved = await saveJobTitle(user.id, jobTitle, attr(user, "job_title"))
      onSaved(saved)
      setDraft(null)
      setMessage({ tone: "green", text: "직책을 저장했습니다." })
    } catch (error) {
      setMessage({ tone: "red", text: error.message })
      onRefresh()
    } finally {
      saving.current = false
      setBusy(false)
    }
  }
  const fields = person ? [
    ["이름", displayName(user)],
    ["직급", attr(user, "grdName")],
    ...(!editing ? [["직책", attr(user, "job_title")]] : []),
    ["EPID", user.username],
    ["로그인 ID", attr(user, "loginid")],
    ["이메일", user.email],
    ["사번", attr(user, "sabun")],
    ["사내 부서", attr(user, "deptname")],
    ["소속 팀", sdwt.team],
    ["라인", sdwt.line],
    ["분임조(파트·SDWT)", sdwt.name],
  ] : []

  return (
    <Dialog open={Boolean(person)} onOpenChange={(open) => { if (!open) close() }}>
      <DialogContent showCloseButton={!busy} onEscapeKeyDown={(event) => { if (saving.current) event.preventDefault() }}
        onPointerDownOutside={(event) => { if (saving.current) event.preventDefault() }} onCloseAutoFocus={(event) => {
        event.preventDefault()
        const trigger = triggerRef.current
        const fallback = document.querySelector('[aria-label="조직도 표시 영역"] button[aria-pressed="true"]')
        const target = trigger?.isConnected ? trigger : fallback
        target?.focus()
      }}>
        <DialogHeader>
          <DialogTitle>사용자 상세정보</DialogTitle>
          <DialogDescription>구성원의 인사 정보와 소속을 확인합니다.</DialogDescription>
        </DialogHeader>
        {message ? <Alert tone={message.tone}>{message.text}</Alert> : null}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
          {fields.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 break-all font-medium">{value || "-"}</dd>
            </div>
          ))}
          {editing ? <div className="col-span-2 min-w-0">
            <dt><Label htmlFor="iam-job-title">직책</Label></dt>
            <dd className="mt-2 flex flex-col gap-2">
              <Input id="iam-job-title" list="iam-job-titles" maxLength={JOB_TITLE_MAX_LENGTH} value={jobTitle}
                disabled={busy} placeholder="예: PL, 파트장" aria-describedby="iam-job-title-hint"
                onChange={(event) => { setDraft(event.target.value); setMessage(null) }} />
              <datalist id="iam-job-titles"><option value="PL" /><option value="파트장" /></datalist>
              <p id="iam-job-title-hint" className="text-xs text-muted-foreground">PL은 현재 소속 라인의 대표, 파트장은 현재 소속 분임조(파트·SDWT)의 대표입니다. 비우고 저장하면 해제됩니다.</p>
            </dd>
          </div> : null}
        </dl>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={close}>닫기</Button>
          {editing ? <Button disabled={busy || !changed} onClick={save}>{busy ? "저장 중…" : "직책 저장"}</Button> : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 이름·EPID로 사용자를 찾아 이 SDWT 소속으로 옮깁니다. */
function AddPerson({ busy, existing, onAdd }) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState(null)
  const shown = (results ?? []).filter((user) => !existing.includes(user.id))

  return (
    <div className="space-y-2 rounded-md border border-dashed p-2">
      <form className="flex gap-2" onSubmit={async (event) => {
        event.preventDefault()
        setResults(query.trim() ? await searchUsers(query.trim()) : [])
      }}>
        <Input className="h-8 min-w-0 flex-1" aria-label="추가할 사용자 검색" placeholder="사람 추가: EPID·이름·이메일" value={query} onChange={(event) => setQuery(event.target.value)} />
        <Button type="submit" variant="outline" className="h-8">검색</Button>
      </form>
      {results ? (
        <ul className="max-h-40 divide-y overflow-auto rounded border">
          {shown.map((user) => (
            <li key={user.id} className="flex items-center gap-2 px-2 py-1 text-sm">
              <span className="min-w-0 flex-1 truncate">
                {displayName(user)} <span className="text-xs text-muted-foreground">{user.username} · {attr(user, "user_sdwt_prod") || "소속 없음"}</span>
              </span>
              <Button variant="outline" className="h-7 px-2 text-xs" disabled={busy} onClick={() => {
                if (!window.confirm(`${displayName(user)}의 소속을 이 SDWT로 바꿀까요? 이전 소속에서는 빠집니다.`)) return
                onAdd(user)
                setResults((list) => list.filter((item) => item.id !== user.id))
              }}>추가</Button>
            </li>
          ))}
          {shown.length === 0 ? <li className="px-2 py-1.5 text-xs text-muted-foreground">추가할 사용자가 없습니다.</li> : null}
        </ul>
      ) : null}
    </div>
  )
}

/** 같은 팀의 다른 라인으로 옮깁니다(수정 모드에서만). */
function MoveLine({ sdwt, team, busy, onMove }) {
  const [target, setTarget] = useState("")
  return (
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <h4 className="text-sm font-semibold">다른 라인으로 이동</h4>
      <p className="text-xs text-muted-foreground">같은 팀 안에서만 옮깁니다. 소속 구성원과 역할은 그대로이고 라인 전체 역할의 범위가 바뀝니다.</p>
      <div className="flex gap-2">
        <Select className="min-w-0 flex-1" aria-label="이동할 라인" value={target} onChange={(event) => setTarget(event.target.value)}>
          <option value="">이동할 라인</option>
          {team.lines.filter((line) => line.name !== sdwt.line).map((line) => <option key={line.id} value={line.name}>{line.name}</option>)}
        </Select>
        <Button disabled={!target || busy} onClick={() => {
          const line = team.lines.find((item) => item.name === target)
          if (window.confirm(`${sdwt.name}을(를) ${line.name} 라인으로 옮길까요? 소속 구성원의 라인 속성도 바뀝니다.`)) onMove(line)
        }}>이동</Button>
      </div>
    </div>
  )
}

/** SDWT 추가 입력입니다. 팀은 비우면 지금 보고 있는 팀입니다. */
function AddForm({ org, team, onPreview }) {
  const [teamName, setTeamName] = useState("")
  const [line, setLine] = useState("")
  const [sdwt, setSdwt] = useState("")
  const targetTeam = teamName || team?.name || ""

  return (
    <div className="flex flex-col gap-2">
      <Input list="iam-teams" aria-label="팀" placeholder={team ? `팀 (비우면 ${team.name})` : "팀 (예: TEAM-1)"} value={teamName} onChange={(e) => setTeamName(e.target.value)} />
      <datalist id="iam-teams">{org.teams.map((item) => <option key={item.id} value={item.name} />)}</datalist>
      <Input list="iam-lines" aria-label="라인" placeholder="라인 (예: LINE-1)" value={line} onChange={(e) => setLine(e.target.value)} />
      <datalist id="iam-lines">
        {[...new Set(org.lines.filter((item) => item.team === targetTeam).map((item) => item.name))].map((name) => <option key={name} value={name} />)}
      </datalist>
      <Input aria-label="SDWT" placeholder="SDWT (예: SDWT-A)" value={sdwt} onChange={(e) => setSdwt(e.target.value)} />
      <Button variant="outline" onClick={() => {
        if (![targetTeam, line, sdwt].every(validGroupName)) {
          onPreview("직접 입력", [], ["팀·라인·SDWT 이름을 확인하세요. 빈 값, 앞뒤 공백, '/', ':'는 쓸 수 없습니다."])
          return
        }
        onPreview("직접 입력", [{ sdwt, line, team: targetTeam }])
      }}>미리보기</Button>
    </div>
  )
}

/** 팀·라인·SDWT를 만드는 모달입니다. 입력(children)이 미리보기를 요청하면 계획을 보여 주고 적용합니다. */
function CreateDialog({ open, onOpenChange, title, description, orgRoot, orgUuid, onDone, children }) {
  const [pending, setPending] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  const preview = (source, items, errors = []) => {
    setResult(null)
    setPending({ source, ...(errors.length ? { creates: [], sdwts: [], errors } : planOrg(orgRoot, items)) })
  }

  const apply = async () => {
    setBusy(true)
    let progress = "시작 전"
    try {
      await createSdwts(orgUuid, pending, (step) => {
        progress = step
      })
      const text = `그룹 ${pending.creates.length}개를 만들고 새 SDWT ${pending.sdwts.length}개의 소속별 역할을 준비했습니다.`
      setPending(null)
      setResult({ tone: "green", text })
      await onDone(text)
    } catch (error) {
      // 다시 적용하면 이미 만든 그룹·역할은 건너뜁니다. 그룹만 있고 역할이 빠졌으면 make keycloak-org-sync로 맞춥니다.
      setResult({ tone: "red", text: `${progress}에서 중단: ${error.message}. 원인을 해결한 뒤 make keycloak-org-sync로 맞추세요.` })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => {
      if (!next) {
        setPending(null)
        setResult(null)
      }
      onOpenChange(next)
    }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children(preview)}
        {pending ? (
          <div className="space-y-2 text-sm">
            <p className="text-xs text-muted-foreground">{pending.source}</p>
            {pending.errors.length > 0 ? (
              <div className="space-y-1">
                <p className="font-medium text-destructive">오류가 있어 적용할 수 없습니다.</p>
                <ul className="list-disc space-y-0.5 pl-5 text-destructive">{pending.errors.map((error) => <li key={error}>{error}</li>)}</ul>
              </div>
            ) : pending.creates.length === 0 ? (
              <p className="text-muted-foreground">모두 이미 있습니다. 바꿀 것이 없습니다.</p>
            ) : (
              <>
                <p>그룹 {pending.creates.length}개를 만들고, 새 SDWT {pending.sdwts.length}개에 소속별 역할(조회·일반·관리자)을 만들어 라인·팀 전체 역할에 넣습니다.</p>
                <ul className="max-h-48 overflow-auto rounded border bg-muted/40 p-2 font-mono text-xs">
                  {pending.creates.map((path) => <li key={path}>{path}</li>)}
                </ul>
              </>
            )}
          </div>
        ) : null}
        {result ? <Alert tone={result.tone}>{result.text}</Alert> : null}
        <DialogFooter>
          <Button variant="ghost" disabled={busy} onClick={() => onOpenChange(false)}>닫기</Button>
          <Button disabled={busy || !pending || pending.errors.length > 0 || pending.creates.length === 0} onClick={apply}>
            {busy ? "적용 중…" : "적용"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
