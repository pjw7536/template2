import { describe, expect, it } from "vitest"

import { displayName, displayProfile, membersByJobTitle, summarizeMembers } from "./users.js"

it("구성원 표시 이름과 로그인 ID를 조합하고 EPID를 표시값으로 사용하지 않습니다", () => {
  expect(displayName({ username: "90000001", attributes: { display_name: ["홍길동"], loginid: ["gildong.hong"] } }))
    .toBe("홍길동(gildong.hong)")
  expect(displayName({ username: "90000001", attributes: { loginid: ["gildong.hong"] } })).toBe("gildong.hong")
  expect(displayProfile({ display_name: "홍길동" }, { attributes: { loginid: ["gildong.hong"] } }))
    .toEqual({ display_name: "홍길동", loginid: "gildong.hong" })
  expect(displayName({ username: "90000001" })).toBe("-")
})

const member = (id, grade) => ({ user: { id, attributes: grade === undefined ? {} : { grdName: [grade] } } })

describe("조직 인원 집계", () => {
  it("여러 파트에 같은 사용자가 있어도 라인 전체에서 한 번만 센다", () => {
    const summary = summarizeMembers([member("a", "수석"), member("b", "책임"), member("a", "수석"), member("c", "책임")])
    expect(summary.total).toBe(3)
    expect(summary.grades).toEqual([{ name: "수석", count: 1 }, { name: "책임", count: 2 }])
    expect(summary.grades.reduce((total, grade) => total + grade.count, 0)).toBe(summary.total)
  })

  it("공백을 정리하고 직급이 없는 구성원도 전체 인원에 포함한다", () => {
    expect(summarizeMembers([member("a", " 책임 "), member("b", "책임"), member("c"), member("d", " ")]))
      .toEqual({ total: 4, grades: [{ name: "책임", count: 2 }, { name: "미등록", count: 2 }] })
  })

  it("빈 조직은 0명으로 집계한다", () => {
    expect(summarizeMembers([])).toEqual({ total: 0, grades: [] })
  })
})

describe("직책별 담당자", () => {
  it("직급·권한을 직책으로 해석하지 않고 사용자 중복을 제거한다", () => {
    const leader = { user: { id: "leader", attributes: { grdName: ["수석"], job_title: ["PL"] } }, sdwt: { name: "A" } }
    const ordinary = { user: { id: "ordinary", attributes: { grdName: ["파트장"] }, roles: ["admin"] } }
    expect(membersByJobTitle([leader, leader, ordinary])).toEqual([
      { title: "PL", people: [leader] }, { title: "파트장", people: [] },
    ])
  })

  it("파트장과 다른 직책도 입력한 값으로 묶는다", () => {
    const partHead = { user: { id: "a", attributes: { job_title: [" 파트장 "] } } }
    const teamHead = { user: { id: "b", attributes: { job_title: ["팀장"] } } }
    expect(membersByJobTitle([partHead, teamHead])).toEqual([
      { title: "PL", people: [] }, { title: "파트장", people: [partHead] }, { title: "팀장", people: [teamHead] },
    ])
  })
})
