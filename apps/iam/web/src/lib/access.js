/**
 * 앱 역할(Keycloak client role) 기반 권한 매트릭스 계산입니다.
 *
 * 역할 규칙(deploy/keycloak/access/catalog.json → make keycloak-access-apply)
 * - 단일 앱: viewer ⊂ user ⊂ admin
 * - 기능이 여러 개인 앱(Portal): <기능>:viewer ⊂ <기능>:user ⊂ <기능>:admin, 묶음 all:viewer·all:user·all:admin
 * - open 앱·기능의 viewer는 realm 기본 역할이라 모든 사용자가 받습니다.
 * 소속별 데이터 범위는 앱 역할이 아니라 소속별 역할(client org)로 정합니다.
 * 카탈로그는 /iam 그룹 속성 iam.catalog에 255자 이하 조각("000:..." 순번)으로 저장됩니다.
 */

export const LEVELS = ["viewer", "user", "admin"]
export const LEVEL_LABELS = { viewer: "조회", user: "일반", admin: "관리자" }

/** 그룹 속성 조각을 순번대로 이어 카탈로그 JSON으로 읽습니다. */
export function readCatalog(values) {
  if (!values?.length) throw new Error("Etch Members 카탈로그가 없습니다. make keycloak-access-apply로 먼저 반영하세요.")
  const text = [...values].sort().map((value) => value.slice(4)).join("")
  const catalog = JSON.parse(text)
  if (!Array.isArray(catalog.apps)) throw new Error("Etch Members 카탈로그 형식이 올바르지 않습니다.")
  return catalog
}

const levelRoles = (prefix) => Object.fromEntries(LEVELS.map((level) => [level, `${prefix}${level}`]))

/** 카탈로그를 매트릭스 열로 바꿉니다. */
export function buildColumns(catalog) {
  const columns = []
  for (const app of catalog.apps) {
    if (app.group) {
      columns.push({ key: app.group, label: app.name, group: app.group, infra: Boolean(app.infra), levels: ["admin"] })
      continue
    }
    const base = { client: app.client, uuid: app.uuid, levels: LEVELS }
    if (app.features) {
      columns.push({ ...base, key: app.client, label: `${app.name} 전체`, roles: levelRoles("all:"), closed: false, bundle: true })
      for (const feature of app.features) {
        columns.push({
          ...base,
          key: `${app.client}.${feature.key}`,
          label: feature.name,
          roles: levelRoles(`${feature.key}:`),
          closed: feature.default === "closed",
        })
      }
    } else {
      columns.push({
        ...base, key: app.client, label: app.name, roles: levelRoles(""), closed: app.default === "closed",
      })
    }
  }
  return columns
}

/** 사용자 권한 묶음: clients[clientId] = { direct: Set, effective: Set }, groups = Set(경로) */
function highest(roles, has) {
  for (let index = LEVELS.length - 1; index >= 0; index -= 1) {
    if (has(roles[LEVELS[index]])) return LEVELS[index]
  }
  return null
}

/**
 * 셀 상태입니다.
 * source: direct(이 사용자에게 직접 부여) | inherited(SDWT 앱 역할·기본 역할·묶음 역할로 받음) | none | unavailable
 */
export function cellState(column, access) {
  if (column.group) {
    const member = access.groups.has(column.group)
    return { level: member ? "admin" : null, direct: member ? "admin" : null, source: member ? "direct" : "none" }
  }
  const client = access.clients[column.client]
  if (!client) return { level: null, direct: null, source: "unavailable" }
  const level = highest(column.roles, (role) => client.effective.has(role))
  const direct = highest(column.roles, (role) => client.direct.has(role))
  return {
    level,
    direct,
    source: level === null ? "none" : direct === level ? "direct" : "inherited",
  }
}

/** 직접 부여를 { level(null이면 없음) }로 바꾸기 위한 역할 추가·제거 목록입니다. */
export function planChange(column, access, { level }) {
  if (column.group) {
    const member = access.groups.has(column.group)
    return { add: level && !member ? [column.group] : [], remove: !level && member ? [column.group] : [] }
  }
  const direct = access.clients[column.client]?.direct ?? new Set()
  const managed = LEVELS.map((name) => column.roles[name])
  const owned = managed.filter((role) => direct.has(role))
  const wanted = level ? [column.roles[level]] : []
  return { add: wanted.filter((role) => !owned.includes(role)), remove: owned.filter((role) => !wanted.includes(role)) }
}
