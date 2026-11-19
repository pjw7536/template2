import { X } from "lucide-react"
import { useEffect, useState } from "react"

import { NativeSelect } from "@/components/NativeSelect"
import { EMPTY_PICK, OrgPicker, pickOf } from "@/components/OrgPicker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { applyAffiliation, grantOrgRole, logoutUser, revokeOrgRole, userGroups, userOrgRoles } from "@/lib/api"
import { LEVEL_NAMES, LEVELS, orgRoleName, parseOrgRole, planAffiliation, sdwtLevels } from "@/lib/plan"
import { attr, displayName } from "@/lib/users"

/** 사용자 한 명의 소속(SDWT 하나)과 소속별 역할을 바꾸는 오른쪽 패널입니다. */
export default function UserPanel({ user, org, orgUuid, onClose, onSaved, onGroupsChanged }) {
  const [groups, setGroups] = useState(null)
  const [roles, setRoles] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const [affiliation, setAffiliation] = useState(() => pickOf(org, attr(user, "user_sdwt_prod")))
  // 사용자가 직접 고르기 전에는 저장하지 않습니다. 현재 SDWT가 조직도에 없으면 선택이 비어 보여도 소속을 지우지 않습니다.
  const [touched, setTouched] = useState(false)
  const currentSdwt = attr(user, "user_sdwt_prod")
  const unknownCurrent = Boolean(currentSdwt && !org.sdwts.has(currentSdwt))
  const [rolePick, setRolePick] = useState(EMPTY_PICK)
  const [level, setLevel] = useState("viewer")
  // 팀을 고르지 않으면 소속 없음, 팀만 고르고 SDWT를 아직 고르지 않았으면 저장할 수 없습니다.
  const newSdwt = affiliation.team ? affiliation.sdwt : ""
  const incomplete = Boolean(affiliation.team && !affiliation.sdwt)

  const refresh = () => Promise.all([userGroups(user.id), userOrgRoles(user.id, orgUuid)])

  useEffect(() => {
    let alive = true
    Promise.all([userGroups(user.id), userOrgRoles(user.id, orgUuid)])
      .then(([nextGroups, nextRoles]) => {
        if (!alive) return
        setGroups(nextGroups)
        setRoles(nextRoles)
      })
      .catch((error) => alive && setMessage({ error: true, text: error.message }))
    return () => {
      alive = false
    }
  }, [user.id, orgUuid])

  const paths = (groups ?? []).map((group) => group.path)
  const plan = planAffiliation({ attributes: user.attributes, groupPaths: paths, newSdwt, org })
  const direct = (roles?.direct ?? []).map((name) => ({ name, ...parseOrgRole(name) })).sort((a, b) => a.name.localeCompare(b.name))
  const effective = Object.entries(sdwtLevels(roles?.effective ?? [])).sort(([a], [b]) => a.localeCompare(b))
  // 고른 범위: SDWT까지 고르면 SDWT, 라인까지면 라인 전체, 팀만 고르면 팀 전체입니다.
  const target = rolePick.sdwt ? { sdwt: rolePick.sdwt } : rolePick.line ? { team: rolePick.team, line: rolePick.line } : { team: rolePick.team }
  const roleName = rolePick.team ? orgRoleName(target, level) : ""

  const run = async (action, success) => {
    setBusy(true)
    setMessage(null)
    try {
      await action()
      setMessage({ text: success })
    } catch (error) {
      setMessage({ error: true, text: error.message })
    } finally {
      const next = await refresh().catch(() => null)
      if (next) {
        setGroups(next[0])
        setRoles(next[1])
      }
      onGroupsChanged?.()
      setBusy(false)
    }
  }

  return (
    <Card className="flex h-full min-h-0 w-[30rem] flex-col gap-0 overflow-hidden py-0">
      <CardHeader className="flex shrink-0 flex-row items-start justify-between gap-2 border-b py-4">
        <div className="min-w-0">
          <CardTitle className="truncate">{displayName(user)}</CardTitle>
          <CardDescription className="truncate">
            {[user.username, attr(user, "loginid"), attr(user, "deptname")].filter(Boolean).join(" · ")}
          </CardDescription>
        </div>
        <Button variant="ghost" size="icon" className="size-8" onClick={onClose} aria-label="닫기">
          <X className="size-4" />
        </Button>
      </CardHeader>
      <CardContent className="grid min-h-0 flex-1 content-start gap-6 overflow-auto py-4">
        {message ? (
          <p role={message.error ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${message.error ? "border-destructive/30 text-destructive" : "bg-muted/40"}`}>
            {message.text}
          </p>
        ) : null}

        <section className="grid gap-2">
          <h3 className="text-sm font-semibold">소속</h3>
          <dl className="grid grid-cols-3 overflow-hidden rounded-md border text-sm">
            {[["팀(부서)", "deptname"], ["라인", "line_id"], ["SDWT", "user_sdwt_prod"]].map(([label, key]) => (
              <div key={key} className="border-r px-3 py-1.5 last:border-r-0">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="truncate font-medium" title={attr(user, key)}>{attr(user, key) || "-"}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-muted-foreground">
            소속은 한 사람당 SDWT 하나입니다. 바꾸면 이전 SDWT 그룹에서 빠지고 새 SDWT 그룹에 들어가며, 소속 SDWT의 일반 역할은 자동으로 따라옵니다. 아래 소속별 역할은 그대로입니다.
          </p>
          <div className="flex gap-2">
            <OrgPicker org={org} value={affiliation} placeholders={{ team: "소속 없음" }} onChange={(next) => {
              setAffiliation(next)
              setTouched(true)
            }} />
            <Button
              disabled={busy || !groups || !touched || incomplete || Boolean(plan.error) || !plan.changed}
              onClick={() => run(async () => {
                const attributes = await applyAffiliation(user, groups, plan)
                onSaved({ ...user, attributes })
              }, "소속을 저장했습니다. 사용자가 다시 로그인하면 앱에 반영됩니다.")}
            >
              저장
            </Button>
          </div>
          {unknownCurrent && !touched ? (
            <p className="text-xs text-chart-4">현재 SDWT({currentSdwt})가 조직도(팀 → 라인 → SDWT)에 없습니다. 새 SDWT를 고르거나 소속 없음을 고른 뒤 저장하세요.</p>
          ) : null}
          {plan.error ? <p className="text-xs text-destructive">{plan.error}</p> : null}
          {incomplete ? <p className="text-xs text-muted-foreground">라인과 SDWT까지 고르세요.</p> : null}
          {plan.teamMismatch && !incomplete ? (
            <p className="text-xs text-chart-4">사내 부서({attr(user, "deptname")})와 다른 팀({plan.team})의 SDWT입니다. 팀은 사내 부서로 정해지므로 인사 정보를 확인하세요.</p>
          ) : null}
          {plan.changed && !plan.error ? (
            <ul className="grid gap-0.5 font-mono text-xs text-muted-foreground">
              {plan.remove.map((path) => <li key={path}>− {path}</li>)}
              {plan.add.map((path) => <li key={path}>+ {path}</li>)}
            </ul>
          ) : null}
        </section>

        <section className="grid gap-2">
          <h3 className="text-sm font-semibold">소속별 역할</h3>
          <p className="text-xs text-muted-foreground">
            다른 SDWT 지원이나 관리자처럼 소속과 별개로 받는 역할입니다. 라인·팀 전체 역할은 그 아래 모든 SDWT 역할을 포함합니다.
          </p>
          <ul className="divide-y rounded-md border">
            {currentSdwt && org.sdwts.has(currentSdwt) ? (
              <li className="flex items-center gap-2 px-3 py-1.5 text-sm">
                <span className="min-w-0 truncate">{currentSdwt}</span>
                <Badge variant="outline">{LEVEL_NAMES.user}</Badge>
                <span className="ml-auto text-xs text-muted-foreground">소속이라 자동</span>
              </li>
            ) : null}
            {direct.map((role) => (
              <li key={role.name} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                <span className="min-w-0 truncate" title={role.name}>{role.label ?? role.name}</span>
                {role.level ? <Badge variant={role.level === "admin" ? "default" : "secondary"}>{LEVEL_NAMES[role.level]}</Badge> : null}
                <Button variant="ghost" size="sm" className="ml-auto h-7 text-destructive hover:text-destructive" disabled={busy}
                  onClick={() => run(() => revokeOrgRole(user.id, orgUuid, role.name), `${role.name} 역할을 회수했습니다.`)}>
                  회수
                </Button>
              </li>
            ))}
            {roles && direct.length === 0 && !currentSdwt ? <li className="px-3 py-2 text-sm text-muted-foreground">역할 없음</li> : null}
            {roles === null ? <li className="px-3 py-2 text-sm text-muted-foreground">불러오는 중…</li> : null}
          </ul>
          <p className="text-xs font-medium text-muted-foreground">역할 부여 (라인을 고르지 않으면 팀 전체, SDWT를 고르지 않으면 라인 전체)</p>
          <div className="flex gap-2">
            <OrgPicker org={org} value={rolePick} onChange={setRolePick} placeholders={{ line: "팀 전체", sdwt: "라인 전체" }} />
            <NativeSelect value={level} onChange={(event) => setLevel(event.target.value)} aria-label="등급">
              {LEVELS.map((name) => <option key={name} value={name}>{LEVEL_NAMES[name]}</option>)}
            </NativeSelect>
          </div>
          <Button variant="outline" className="justify-self-end" disabled={busy || !roleName || roles?.direct.includes(roleName)}
            onClick={() => run(() => grantOrgRole(user.id, orgUuid, roleName), `${roleName} 역할을 부여했습니다.`)}>
            {roleName ? `${roleName} 부여` : "역할 부여"}
          </Button>
          <div className="grid gap-1">
            <p className="text-xs font-medium text-muted-foreground">SDWT별 적용 결과 (앱은 이 등급과 앱 역할 중 낮은 쪽으로 판단)</p>
            <div className="flex flex-wrap gap-1">
              {effective.map(([sdwt, value]) => (
                <Badge key={sdwt} variant="outline" className="font-normal">{sdwt} · {LEVEL_NAMES[value]}</Badge>
              ))}
              {roles && effective.length === 0 ? <span className="text-xs text-muted-foreground">볼 수 있는 SDWT 없음</span> : null}
            </div>
          </div>
        </section>

        <section className="grid gap-2">
          <h3 className="text-sm font-semibold">세션</h3>
          <p className="text-xs text-muted-foreground">권한을 즉시 회수해야 할 때 모든 로그인 세션을 끊습니다. 다음 요청부터 다시 로그인해야 하며 새 권한이 적용됩니다.</p>
          <Button variant="outline" className="justify-self-start text-destructive hover:text-destructive" disabled={busy}
            onClick={() => {
              if (window.confirm(`${displayName(user)}의 모든 세션을 종료할까요?`)) run(() => logoutUser(user.id), "모든 세션을 종료했습니다.")
            }}>
            세션 종료
          </Button>
        </section>
      </CardContent>
    </Card>
  )
}
