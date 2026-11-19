import { useState } from "react"
import { applyAffiliation, findUser, userGroups } from "../lib/api.js"
import { readUserCsv } from "../lib/csv.js"
import { planAffiliation } from "../lib/plan.js"
import { Alert, Badge, Button, Card, FilePicker } from "../components/ui.jsx"
import { displayName } from "@/lib/users"

const STATUS = {
  change: ["blue", "변경"],
  same: ["gray", "변경 없음"],
  missing: ["amber", "사용자 없음"],
  invalid: ["red", "SDWT 없음"],
  done: ["green", "완료"],
  failed: ["red", "실패"],
}

/** 사용자 소속 CSV를 미리보고 한 번에 적용하는 화면입니다. */
export default function UploadPage({ org }) {
  const [rows, setRows] = useState(null)
  const [errors, setErrors] = useState([])
  const [source, setSource] = useState("")
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = async (text, name) => {
    const parsed = readUserCsv(text)
    setSource(name)
    setErrors(parsed.errors)
    setRows(null)
    if (parsed.errors.length) return
    setLoading(true)
    try {
      const prepared = []
      for (const item of parsed.items) {
        const user = await findUser(item.userid)
        if (!user) {
          prepared.push({ ...item, status: "missing" })
          continue
        }
        const groups = await userGroups(user.id)
        const plan = planAffiliation({ attributes: user.attributes, groupPaths: groups.map((g) => g.path), newSdwt: item.sdwt, org })
        const status = plan.error ? "invalid" : plan.changed ? "change" : "same"
        prepared.push({ ...item, user, groups, plan, status })
      }
      setRows(prepared)
    } catch (error) {
      setErrors([error.message])
    } finally {
      setLoading(false)
    }
  }

  const apply = async () => {
    setBusy(true)
    const next = [...rows]
    for (let index = 0; index < next.length; index += 1) {
      const row = next[index]
      if (row.status !== "change") continue
      try {
        await applyAffiliation(row.user, row.groups, row.plan)
        next[index] = { ...row, status: "done" }
      } catch (error) {
        next[index] = { ...row, status: "failed", message: error.message }
      }
      setRows([...next])
    }
    setBusy(false)
  }

  const count = (status) => rows?.filter((row) => row.status === status).length ?? 0

  return (
    <Card
      title="사용자 소속 업로드"
      description="헤더 userid,user_sdwt_prod (userid = EPID, SDWT가 비면 소속 없음). 다른 열은 무시합니다. 바꾸면 이전 SDWT 그룹에서 빠지고 새 SDWT 그룹에 들어갑니다(소속 SDWT 일반 역할은 자동). 소속별 역할은 그대로입니다."
      actions={<FilePicker label="CSV 파일 선택" onText={load} />}
    >
      <div className="space-y-3">
        {errors.length > 0 && (
          <Alert>
            <p className="font-medium">{source}: 적용할 수 없습니다.</p>
            <ul className="list-disc pl-5">{errors.map((error) => <li key={error}>{error}</li>)}</ul>
          </Alert>
        )}
        {loading && <p className="text-sm text-muted-foreground">사용자를 확인하는 중…</p>}
        {!rows && !loading && errors.length === 0 && <p className="text-sm text-muted-foreground">CSV 파일을 선택하면 적용 전에 변경 내용을 보여 줍니다.</p>}
        {rows && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{source}</span>
              <Badge tone="blue">변경 {count("change")}</Badge>
              <Badge>변경 없음 {count("same")}</Badge>
              <Badge tone="amber">사용자 없음 {count("missing")}</Badge>
              <Badge tone="red">SDWT 없음 {count("invalid")}</Badge>
              {count("done") > 0 && <Badge tone="green">완료 {count("done")}</Badge>}
              {count("failed") > 0 && <Badge tone="red">실패 {count("failed")}</Badge>}
              <Button className="ml-auto" disabled={busy || count("change") === 0} onClick={apply}>
                {busy ? "적용 중…" : `변경 ${count("change")}건 적용`}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">사용자 없음은 아직 사내 로그인을 하지 않은 사용자입니다. 로그인한 뒤 다시 올리면 반영됩니다.</p>
            <div className="max-h-[60vh] overflow-auto rounded-md border border">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 border-b border bg-card text-xs text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">행</th>
                    <th className="px-3 py-2 font-medium">EPID</th>
                    <th className="px-3 py-2 font-medium">이름</th>
                    {["현재 팀(부서)", "현재 라인", "현재 SDWT", "변경 팀", "변경 라인", "변경 SDWT"].map((label) => (
                      <th key={label} className="px-3 py-2 font-medium">{label}</th>
                    ))}
                    <th className="px-3 py-2 font-medium">그룹 변경</th>
                    <th className="px-3 py-2 font-medium">상태</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {rows.map((row) => {
                    const [tone, label] = STATUS[row.status]
                    return (
                      <tr key={row.userid}>
                        <td className="px-3 py-1.5 text-xs text-muted-foreground">{row.number}</td>
                        <td className="px-3 py-1.5 font-mono text-xs">{row.userid}</td>
                        <td className="px-3 py-1.5">{row.user ? displayName(row.user) : "-"}</td>
                        {["deptname", "line_id", "user_sdwt_prod"].map((key) => (
                          <td key={key} className="px-3 py-1.5 text-muted-foreground">{row.user?.attributes?.[key]?.[0] || "-"}</td>
                        ))}
                        {[org.sdwts.get(row.sdwt)?.team, org.sdwts.get(row.sdwt)?.line, row.sdwt].map((value, index) => (
                          <td key={index} className="px-3 py-1.5">{value || (row.sdwt ? "-" : "소속 없음")}</td>
                        ))}
                        <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">
                          {row.plan?.remove?.map((path) => <div key={path}>− {path}</div>)}
                          {row.plan?.add?.map((path) => <div key={path}>+ {path}</div>)}
                        </td>
                        <td className="px-3 py-1.5">
                          <Badge tone={tone}>{label}</Badge>
                          {row.message && <div className="mt-0.5 text-xs text-destructive">{row.message}</div>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}
