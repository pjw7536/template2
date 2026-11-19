/**
 * 소속(/org 그룹)과 소속별 역할(client org 역할)을 계산하는 순수 함수입니다.
 *
 * 소속: /org/<팀>/<라인>/<SDWT> 그룹. 사람당 SDWT 하나. SDWT 그룹 가입이 곧 소속입니다.
 * 소속별 역할(client org):
 *   sdwt:<SDWT>:<등급>, team:<팀>:line:<라인>:<등급>, team:<팀>:<등급>(라인·팀 역할은 그 아래 SDWT 역할을 포함)
 *   등급은 viewer|user|admin입니다.
 *   소속 SDWT의 user 역할(sdwt:<SDWT>:user)은 SDWT 그룹에 연결되어 자동으로 받습니다.
 * 소속 변경: 이전 SDWT 그룹에서 빠지고 새 SDWT 그룹에 가입, 속성 user_sdwt_prod·line_id 갱신.
 * 팀은 사내 부서(deptname)와 같은 값이며 사내 로그인 때 맞춰지므로 여기서 쓰지 않습니다.
 */

export const ORG_ROOT = "org"
export const LEVELS = ["viewer", "user", "admin"]
export const LEVEL_NAMES = { viewer: "조회", user: "일반", admin: "관리자" }
const RANK = { viewer: 1, user: 2, admin: 3 }

const byName = (a, b) => a.name.localeCompare(b.name)

/** /org 그룹(children 포함)에서 팀·라인·SDWT를 읽습니다. */
export function buildOrg(orgRoot) {
  const teams = []
  const lines = []
  const sdwts = new Map()
  for (const teamGroup of orgRoot?.children ?? []) {
    const team = { name: teamGroup.name, id: teamGroup.id, path: `/${ORG_ROOT}/${teamGroup.name}`, lines: [] }
    for (const lineGroup of teamGroup.children ?? []) {
      const line = { name: lineGroup.name, id: lineGroup.id, team: team.name, path: `${team.path}/${lineGroup.name}`, sdwts: [] }
      for (const sdwtGroup of lineGroup.children ?? []) {
        const sdwt = { name: sdwtGroup.name, id: sdwtGroup.id, team: team.name, line: line.name, path: `${line.path}/${sdwtGroup.name}` }
        line.sdwts.push(sdwt)
        sdwts.set(sdwt.name, sdwt)
      }
      line.sdwts.sort(byName)
      team.lines.push(line)
      lines.push(line)
    }
    team.lines.sort(byName)
    teams.push(team)
  }
  teams.sort(byName)
  return { teams, lines, sdwts }
}

/** 트리를 경로 → 그룹 목록으로 펼칩니다. */
export function flatten(groups, prefix = "", into = new Map()) {
  for (const group of groups) {
    const path = `${prefix}/${group.name}`
    into.set(path, group)
    flatten(group.children ?? [], path, into)
  }
  return into
}

/** 한 SDWT에 필요한 소속 그룹 경로를 상위부터 돌려줍니다. */
export function sdwtPaths({ team, line, sdwt }) {
  const teamPath = `/${ORG_ROOT}/${team}`
  return [teamPath, `${teamPath}/${line}`, `${teamPath}/${line}/${sdwt}`]
}

/** 목록 CSV·추가 입력을 반영하는 데 필요한 소속 그룹 생성 순서와 오류, 새 SDWT 목록을 계산합니다. */
export function planOrg(orgRoot, items) {
  const existing = flatten(orgRoot?.children ?? [], `/${ORG_ROOT}`)
  const wanted = new Map(items.map((item) => [item.sdwt, sdwtPaths(item)[2]]))
  const errors = []
  for (const path of existing.keys()) {
    if (path.split("/").length !== 5) continue
    const name = path.split("/").at(-1)
    if (wanted.has(name) && wanted.get(name) !== path) {
      errors.push(`SDWT '${name}'가 이미 다른 위치(${path})에 있습니다. 라인 이동으로 옮기세요.`)
    }
  }
  if (errors.length) return { creates: [], errors, sdwts: [] }
  const creates = []
  const sdwts = []
  for (const item of items) {
    for (const path of sdwtPaths(item)) {
      if (!existing.has(path) && !creates.includes(path)) creates.push(path)
    }
    if (!existing.has(sdwtPaths(item)[2])) sdwts.push(item)
  }
  return { creates, errors, sdwts }
}

/** 소속별 역할 이름입니다. target: { sdwt } | { team, line } | { team } */
export function orgRoleName(target, level) {
  if (target.sdwt) return `sdwt:${target.sdwt}:${level}`
  if (target.line) return `team:${target.team}:line:${target.line}:${level}`
  return `team:${target.team}:${level}`
}

/** 역할 이름을 { kind, team, line, sdwt, level, label }로 읽습니다. 형식이 다르면 null입니다. */
export function parseOrgRole(name) {
  const parts = name.split(":")
  const level = parts.at(-1)
  if (!LEVELS.includes(level)) return null
  const [kind, value, sub, subValue] = parts
  if (parts.length === 3 && kind === "sdwt") return { kind: "sdwt", sdwt: value, level, label: value }
  if (parts.length === 3 && kind === "team") return { kind: "team", team: value, level, label: `${value} 팀 전체` }
  if (parts.length === 5 && kind === "team" && sub === "line") {
    return { kind: "line", team: value, line: subValue, level, label: `${value} / ${subValue} 라인 전체` }
  }
  return null
}

/**
 * 토큰 org_roles처럼 펼쳐진 역할 이름 목록에서 SDWT별 가장 높은 등급을 구합니다.
 * 앱의 판단 규칙: SDWT S 데이터 = min(앱 역할, 이 값). 값이 없으면 볼 수 없습니다.
 */
export function sdwtLevels(roleNames) {
  const levels = {}
  for (const name of roleNames) {
    const role = parseOrgRole(name)
    if (role?.kind !== "sdwt") continue
    if (!levels[role.sdwt] || RANK[role.level] > RANK[levels[role.sdwt]]) levels[role.sdwt] = role.level
  }
  return levels
}

function first(attributes, name) {
  return attributes?.[name]?.[0] ?? ""
}

/** 그룹 경로 중 소속 그룹(/org/팀/라인/SDWT)만 고릅니다. */
export function affiliationPaths(groupPaths) {
  return groupPaths.filter((path) => path.startsWith(`/${ORG_ROOT}/`) && path.split("/").length === 5)
}

/**
 * 소속을 newSdwt로 바꿀 때의 변경입니다. newSdwt가 빈 값이면 소속 없음입니다.
 * 소속은 하나이므로 다른 소속 그룹은 모두 빠집니다. 소속별 역할(org 역할)은 건드리지 않습니다.
 */
export function planAffiliation({ attributes, groupPaths, newSdwt, org }) {
  const oldSdwt = first(attributes, "user_sdwt_prod")
  const target = newSdwt ? org.sdwts.get(newSdwt) : null
  if (newSdwt && !target) return { error: `SDWT '${newSdwt}'가 없습니다.` }
  const current = affiliationPaths(groupPaths)
  const remove = current.filter((path) => path !== target?.path)
  const add = target && !current.includes(target.path) ? [target.path] : []
  const line = target?.line ?? ""
  const team = target?.team ?? ""
  const attributeChanged = oldSdwt !== (newSdwt ?? "") || first(attributes, "line_id") !== line
  const deptname = first(attributes, "deptname")
  return {
    oldSdwt,
    newSdwt: newSdwt ?? "",
    line,
    team,
    remove,
    add,
    attributeChanged,
    changed: Boolean(remove.length || add.length || attributeChanged),
    // 사내 부서와 다른 팀의 SDWT를 고르면 경고합니다. 저장은 막지 않습니다.
    teamMismatch: Boolean(target && deptname && deptname !== team),
  }
}

/** 기존 속성을 보존하고 소속 속성(SDWT·라인)만 바꿉니다. 팀(deptname)은 바꾸지 않습니다. */
export function withAffiliation(attributes, { newSdwt, line }) {
  const next = { ...(attributes ?? {}) }
  if (newSdwt) {
    next.user_sdwt_prod = [newSdwt]
    next.line_id = [line]
  } else {
    delete next.user_sdwt_prod
    delete next.line_id
  }
  return next
}

/** 새 SDWT에 필요한 소속별 역할 이름과 그 역할을 포함해야 할 라인·팀 역할입니다. */
export function sdwtRolePlan({ team, line, sdwt }) {
  return LEVELS.map((level) => ({
    role: orgRoleName({ sdwt }, level),
    parents: [orgRoleName({ team, line }, level), orgRoleName({ team }, level)],
  }))
}
