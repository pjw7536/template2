import { groupMembers } from "./api.js"
import { keycloak } from "./keycloak.js"

export async function workloadMonth(month, { data, signal } = {}) {
  await keycloak.updateToken(30)
  const response = await fetch(`/api/workload/${encodeURIComponent(month)}`, {
    method: data ? "PUT" : "GET",
    headers: {
      Authorization: `Bearer ${keycloak.token}`,
      ...(data ? { "Content-Type": "application/json" } : {}),
    },
    body: data ? JSON.stringify(data) : undefined,
    cache: "no-store",
    signal,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok || !payload) {
    const error = new Error(payload?.error || "업무 부하 저장 API에 연결할 수 없습니다.")
    error.status = response.status
    throw error
  }
  return payload
}

/** IAM 조직도의 실제 SDWT 구성원을 라인별로 중복 제거해 집계합니다. */
export async function loadLineHeadcount(line) {
  const userIds = new Set()
  const size = 1000
  await Promise.all(line.sdwts.map(async ({ id }) => {
    let first = 0
    let members
    do {
      members = await groupMembers(id, { first, max: size, briefRepresentation: true })
      for (const user of members) userIds.add(user.id)
      first += members.length
    } while (members.length === size)
  }))
  return userIds.size
}
