import { admin } from "./keycloak.js"
import { readCatalog } from "./access.js"
import { attr, JOB_TITLE_MAX_LENGTH } from "./users.js"
import { LEVEL_NAMES, LEVELS, ORG_ROOT, orgRoleName, planAffiliation, sdwtPaths, sdwtRolePlan, withAffiliation } from "./plan.js"

const ALL_ROLE = "org-all"

/** Keycloak Admin API 묶음입니다. 그룹 경로는 /a/b/c 형식입니다. */

const MAX = { max: "1000", briefRepresentation: "true" }

function children(id) {
  return admin(`/groups/${id}/children`, { query: MAX })
}

/** 그룹 아래를 depth 단계까지 읽습니다. */
async function withChildren(group, depth) {
  if (depth <= 0) return group
  const items = await children(group.id)
  return { ...group, children: await Promise.all(items.map((item) => withChildren(item, depth - 1))) }
}

/** 소속 트리 /org와 그 아래 세 단계(팀 → 라인 → SDWT)를 읽습니다. 없으면 null입니다. */
export async function loadOrgRoot() {
  try {
    return await withChildren(await groupByPath(`/${ORG_ROOT}`), 3)
  } catch (error) {
    if (error.status === 404) return null
    throw error
  }
}

export function groupByPath(path) {
  const encoded = path.split("/").filter(Boolean).map(encodeURIComponent).join("/")
  return admin(`/group-by-path/${encoded}`)
}

/** 경로의 마지막 그룹을 만듭니다. 상위 그룹은 이미 있어야 합니다. */
export async function createGroup(path) {
  const parts = path.split("/").filter(Boolean)
  const name = parts.pop()
  if (!parts.length) return admin("/groups", { method: "POST", body: { name } })
  const parent = await groupByPath(`/${parts.join("/")}`)
  return admin(`/groups/${parent.id}/children`, { method: "POST", body: { name } })
}

/* ---------- 소속별 역할(client org) ---------- */

const orgRoles = (orgUuid) => `/clients/${orgUuid}/roles`

/** 역할을 이름으로 읽고, 없으면 만듭니다. */
async function ensureRole(orgUuid, name, description) {
  try {
    return await admin(`${orgRoles(orgUuid)}/${encodeURIComponent(name)}`)
  } catch (error) {
    if (error.status !== 404) throw error
  }
  await admin(orgRoles(orgUuid), { method: "POST", body: { name, description } })
  return admin(`${orgRoles(orgUuid)}/${encodeURIComponent(name)}`)
}

function composites(orgUuid, parent, method, roles) {
  if (!roles.length) return null
  return admin(`${orgRoles(orgUuid)}/${encodeURIComponent(parent)}/composites`, { method, body: roles })
}

/**
 * 새 SDWT 하나의 소속별 역할을 준비합니다(make keycloak-org-sync와 같은 결과).
 * SDWT 역할 3개 생성, 라인·팀 역할과 토큰 묶음(org-all)에 포함, SDWT 그룹에 자기 SDWT 일반 역할 연결.
 */
export async function setupSdwtRoles(orgUuid, item, groupId) {
  const created = {}
  for (const { role, parents } of sdwtRolePlan(item)) {
    const level = role.split(":").at(-1)
    created[level] = await ensureRole(orgUuid, role, `${item.sdwt} ${LEVEL_NAMES[level]}`)
    const [lineRole, teamRole] = parents
    await ensureRole(orgUuid, lineRole, `${item.team} / ${item.line} 라인 전체 ${LEVEL_NAMES[level]}`)
    await ensureRole(orgUuid, teamRole, `${item.team} 팀 전체 ${LEVEL_NAMES[level]}`)
    for (const parent of parents) await composites(orgUuid, parent, "POST", [created[level]])
    // 토큰 묶음(org-all)에는 SDWT 역할만 넣어 토큰 org_roles에 sdwt:… 값만 나가게 합니다.
    await composites(orgUuid, ALL_ROLE, "POST", [created[level]])
  }
  await admin(`/groups/${groupId}/role-mappings/clients/${orgUuid}`, { method: "POST", body: [created.user] })
}

/** 목록(item: { team, line, sdwt })의 소속 그룹 생성(creates)과 새 SDWT의 역할 준비를 적용합니다. */
export async function createSdwts(orgUuid, plan, onProgress = () => {}) {
  for (const [index, path] of plan.creates.entries()) {
    await createGroup(path)
    onProgress(`그룹 ${index + 1}/${plan.creates.length}`)
  }
  for (const [index, item] of plan.sdwts.entries()) {
    const group = await groupByPath(sdwtPaths(item)[2])
    await setupSdwtRoles(orgUuid, item, group.id)
    onProgress(`역할 ${index + 1}/${plan.sdwts.length}`)
  }
}

/**
 * 기존 SDWT 그룹을 다른 라인(target: { id, name, team })으로 옮깁니다.
 * 라인·팀 역할의 하위 역할을 옮기고, 소속 구성원의 line_id를 맞춥니다.
 * 팀(deptname)은 사내 인사 값이므로 바꾸지 않습니다.
 */
export async function moveSdwt(orgUuid, sdwt, target) {
  await admin(`/groups/${target.id}/children`, { method: "POST", body: { id: sdwt.id, name: sdwt.name } })
  for (const level of LEVELS) {
    const role = await ensureRole(orgUuid, orgRoleName({ sdwt: sdwt.name }, level))
    const from = [orgRoleName({ team: sdwt.team, line: sdwt.line }, level), orgRoleName({ team: sdwt.team }, level)]
    const to = [orgRoleName({ team: target.team, line: target.name }, level), orgRoleName({ team: target.team }, level)]
    for (const parent of from.filter((name) => !to.includes(name))) await composites(orgUuid, parent, "DELETE", [role])
    for (const parent of to.filter((name) => !from.includes(name))) {
      await ensureRole(orgUuid, parent)
      await composites(orgUuid, parent, "POST", [role])
    }
  }
  let count = 0
  for (const user of await groupMembers(sdwt.id)) {
    await saveAttributes(user.id, (attributes) => ({ ...attributes, line_id: [target.name] }))
    count += 1
  }
  return count
}

/** 사용자의 소속별 역할: 직접 받은 역할과 펼쳐진 전체 역할(토큰 org_roles와 같음) 이름입니다. */
export async function userOrgRoles(userId, orgUuid) {
  const base = `/users/${userId}/role-mappings/clients/${orgUuid}`
  const [direct, effective] = await Promise.all([admin(base), admin(`${base}/composite`, { query: { briefRepresentation: "true" } })])
  return { direct: direct.map((role) => role.name), effective: effective.map((role) => role.name) }
}

export async function grantOrgRole(userId, orgUuid, name) {
  const role = await admin(`${orgRoles(orgUuid)}/${encodeURIComponent(name)}`)
  return admin(`/users/${userId}/role-mappings/clients/${orgUuid}`, { method: "POST", body: [role] })
}

export async function revokeOrgRole(userId, orgUuid, name) {
  const role = await admin(`${orgRoles(orgUuid)}/${encodeURIComponent(name)}`)
  return admin(`/users/${userId}/role-mappings/clients/${orgUuid}`, { method: "DELETE", body: [role] })
}

/** 역할을 직접 받은 사용자(속성 포함)입니다. 역할이 없으면 빈 목록입니다. */
export async function roleHolders(orgUuid, name) {
  try {
    return await admin(`${orgRoles(orgUuid)}/${encodeURIComponent(name)}/users`, { query: { max: "1000", briefRepresentation: "false" } })
  } catch (error) {
    if (error.status === 404) return []
    throw error
  }
}

/** 그룹의 직접 가입자(속성 포함)입니다. */
export function groupMembers(groupId, page = {}) {
  return admin(`/groups/${groupId}/members`, { query: { max: "1000", briefRepresentation: "false", ...page } })
}

export function searchUsers(search) {
  return admin("/users", { query: { search, max: "50", briefRepresentation: "false" } })
}

export async function findUser(username) {
  const users = await admin("/users", { query: { username, exact: "true", briefRepresentation: "false" } })
  return users.find((user) => user.username === username.toLowerCase()) ?? null
}

export function userGroups(id) {
  return admin(`/users/${id}/groups`, { query: { max: "1000", briefRepresentation: "true" } })
}

export async function joinGroup(userId, path) {
  const group = await groupByPath(path)
  return admin(`/users/${userId}/groups/${group.id}`, { method: "PUT" })
}

/** 그룹 id로 바로 가입시킵니다(경로 조회 없이). */
export function joinGroupById(userId, groupId) {
  return admin(`/users/${userId}/groups/${groupId}`, { method: "PUT" })
}

export function leaveGroup(userId, groupId) {
  return admin(`/users/${userId}/groups/${groupId}`, { method: "DELETE" })
}

/**
 * 저장 직전의 사용자 속성에 update를 적용해 저장하고 저장한 속성을 돌려줍니다.
 * 화면이 들고 있던 이전 속성으로 덮어써서 다른 변경(앱 권한 등)을 잃지 않게 합니다.
 */
export async function saveAttributes(userId, update) {
  const current = await admin(`/users/${userId}`)
  const attributes = update({ ...(current.attributes ?? {}) })
  await admin(`/users/${userId}`, { method: "PUT", body: { ...current, attributes } })
  return attributes
}

/** 직책만 저장하며 동시 변경과 미등록 프로필 때문에 값이 저장되지 않는 경우를 확인합니다. */
export async function saveJobTitle(userId, title, previousTitle = "") {
  if (typeof title !== "string" || title.trim().length > JOB_TITLE_MAX_LENGTH) {
    throw new Error(`직책은 ${JOB_TITLE_MAX_LENGTH}자 이내로 입력하세요.`)
  }
  const next = title.trim()
  await saveAttributes(userId, (attributes) => {
    if (attr({ attributes }, "job_title").trim() !== previousTitle.trim()) {
      throw new Error("다른 관리자가 직책을 변경했습니다. 창을 닫고 다시 열어 확인하세요.")
    }
    if (next) attributes.job_title = [next]
    else delete attributes.job_title
    return attributes
  })
  const saved = await admin(`/users/${userId}`)
  if (attr(saved, "job_title").trim() !== next) {
    throw new Error("직책이 저장되지 않았습니다. Keycloak User Profile의 job_title 설정을 확인하세요.")
  }
  return saved
}

/** planAffiliation 결과를 적용하고 저장한 속성을 돌려줍니다. groups는 userGroups 응답입니다. */
export async function applyAffiliation(user, groups, plan) {
  for (const path of plan.remove) {
    const group = groups.find((item) => item.path === path)
    if (group) await leaveGroup(user.id, group.id)
  }
  for (const path of plan.add) await joinGroup(user.id, path)
  if (!plan.attributeChanged) return user.attributes
  return saveAttributes(user.id, (attributes) => withAffiliation(attributes, plan))
}

/** 화면을 연 뒤 소속이 바뀌었으면 이동을 중단하고, 최신 사용자·그룹으로 소속 변경을 적용합니다. */
export async function moveMemberAffiliation(userId, fromSdwt, newSdwt, org) {
  const source = org.sdwts.get(fromSdwt)
  if (!source || !org.sdwts.has(newSdwt)) throw new Error("이동할 SDWT를 다시 선택하세요.")
  if (fromSdwt === newSdwt) throw new Error("현재 소속과 다른 SDWT를 선택하세요.")
  const [user, groups] = await Promise.all([admin(`/users/${userId}`), userGroups(userId)])
  if (!groups.some((group) => group.path === source.path)) {
    throw new Error("이 사용자의 소속이 변경되었습니다. 구성원 목록을 다시 확인하세요.")
  }
  const plan = planAffiliation({ attributes: user.attributes, groupPaths: groups.map((group) => group.path), newSdwt, org })
  if (plan.error) throw new Error(plan.error)
  return applyAffiliation(user, groups, plan)
}

/** /iam 그룹 속성에 저장된 앱 역할 카탈로그를 읽습니다(make keycloak-access-apply가 저장). */
export async function loadCatalog() {
  const group = await groupByPath("/iam")
  return readCatalog(group.attributes?.["iam.catalog"])
}

/** 매트릭스용 사용자 권한: 앱 client별 직접·유효 역할과 그룹 경로입니다. */
export async function loadAccess(userId, clients) {
  const [mappings, groups, effective] = await Promise.all([
    admin(`/users/${userId}/role-mappings`),
    userGroups(userId),
    Promise.all(clients.map(({ uuid }) => admin(`/users/${userId}/role-mappings/clients/${uuid}/composite`, { query: { briefRepresentation: "true" } }))),
  ])
  const result = {}
  clients.forEach(({ client }, index) => {
    result[client] = {
      direct: new Set((mappings.clientMappings?.[client]?.mappings ?? []).map((role) => role.name)),
      effective: new Set(effective[index].map((role) => role.name)),
    }
  })
  return { clients: result, groups: new Set(groups.map((group) => group.path)), groupList: groups }
}

/** base(사용자·그룹의 client 역할 경로)에서 역할 이름을 실제 역할 표현으로 바꿉니다. */
async function pickRoles(base, names, source) {
  if (!names.length) return []
  const roles = await admin(source === "available" ? `${base}/available` : base)
  const picked = roles.filter((role) => names.includes(role.name))
  if (picked.length !== names.length) throw new Error(`역할 ${names.join(", ")}을 찾지 못했습니다. make keycloak-access-apply를 확인하세요.`)
  return picked
}

async function changeRoles(base, plan) {
  const remove = await pickRoles(base, plan.remove, "assigned")
  if (remove.length) await admin(base, { method: "DELETE", body: remove })
  const add = await pickRoles(base, plan.add, "available")
  if (add.length) await admin(base, { method: "POST", body: add })
}

/** planChange 결과를 사용자에게 적용합니다. 그룹 열은 가입·탈퇴, 역할 열은 직접 역할을 바꿉니다. */
export async function applyChange(userId, column, plan, access) {
  if (column.group) {
    for (const path of plan.remove) {
      const group = access.groupList.find((item) => item.path === path)
      if (group) await leaveGroup(userId, group.id)
    }
    for (const path of plan.add) await joinGroup(userId, path)
    return
  }
  await changeRoles(`/users/${userId}/role-mappings/clients/${column.uuid}`, plan)
}

/** SDWT 그룹에 연결된 앱 역할입니다. 그 SDWT 소속 구성원 모두에게 상속됩니다. 소속별 역할(client org)은 뺍니다. */
export async function groupAppRoles(groupId) {
  const mappings = await admin(`/groups/${groupId}/role-mappings`)
  return Object.entries(mappings.clientMappings ?? {}).filter(([client]) => client !== ORG_ROOT).flatMap(([client, item]) => item.mappings.map((role) => ({ client, name: role.name })))
}

export function changeGroupRoles(groupId, uuid, plan) {
  return changeRoles(`/groups/${groupId}/role-mappings/clients/${uuid}`, plan)
}

/** 사용자의 모든 세션을 끊어 다음 요청부터 다시 로그인하게 합니다(즉시 회수용). */
export function logoutUser(userId) {
  return admin(`/users/${userId}/logout`, { method: "POST" })
}

/** 매트릭스 목록용 사용자 조회입니다. 부서는 deptname 속성 정확 일치입니다. */
export function listUsers({ search, department, first }) {
  const query = { first: String(first), max: "50", briefRepresentation: "false" }
  if (search) query.search = search
  if (department) query.q = `deptname:${department}`
  return admin("/users", { query })
}
