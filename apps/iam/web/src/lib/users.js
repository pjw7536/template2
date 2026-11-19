/** 사용자 표시용 helper입니다. */
export const JOB_TITLE_MAX_LENGTH = 80

export const attr = (user, name) => user?.attributes?.[name]?.[0] ?? ""

export const displayName = (user) =>
  attr(user, "display_name") || [user?.lastName, user?.firstName].filter(Boolean).join("") || user?.username || "-"

/** 실제 소속 구성원을 사용자별로 한 번만 세고, 인사 직급별 인원을 집계합니다. */
export function summarizeMembers(people) {
  const unique = new Map(people.map((entry) => [entry.user.id ?? entry.user.username ?? entry.user, entry.user]))
  const counts = new Map()
  for (const user of unique.values()) {
    const grade = attr(user, "grdName").trim() || "미등록"
    counts.set(grade, (counts.get(grade) ?? 0) + 1)
  }
  const grades = [...counts].map(([name, count]) => ({ name, count })).sort((a, b) => {
    if (a.name === "미등록") return 1
    if (b.name === "미등록") return -1
    return a.name.localeCompare(b.name, "ko")
  })
  return { total: unique.size, grades }
}

/** 권한 역할과 무관하게 직책별 담당자를 묶고, PL·파트장은 미등록 상태도 표시합니다. */
export function membersByJobTitle(people) {
  const unique = new Map(people.map((entry) => [entry.user.id ?? entry.user.username ?? entry.user, entry]))
  const groups = new Map([["PL", []], ["파트장", []]])
  for (const entry of unique.values()) {
    const title = attr(entry.user, "job_title").trim()
    if (!title) continue
    if (!groups.has(title)) groups.set(title, [])
    groups.get(title).push(entry)
  }
  return [...groups].map(([title, members]) => ({
    title,
    people: members.sort((a, b) => displayName(a.user).localeCompare(displayName(b.user), "ko")),
  }))
}
