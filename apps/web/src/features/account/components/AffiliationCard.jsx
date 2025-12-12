import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

function formatLocalDateTime(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const pad = (n) => String(n).padStart(2, "0")
  const year = date.getFullYear()
  const month = pad(date.getMonth() + 1)
  const day = pad(date.getDate())
  const hour = pad(date.getHours())
  const minute = pad(date.getMinutes())
  return `${year}-${month}-${day}T${hour}:${minute}`
}

function isoFromLocalInput(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString()
}

function optionKey(opt) {
  return `${opt.department}||${opt.line}||${opt.user_sdwt_prod}`
}

export function AffiliationCard({
  data,
  onSubmit,
  isSubmitting,
  error,
}) {
  const [selectedKey, setSelectedKey] = useState("")
  const [effectiveFrom, setEffectiveFrom] = useState("")

  const timezoneName = data?.timezone || "Asia/Seoul"
  const options = data?.affiliationOptions || []

  const selected = options.find((opt) => optionKey(opt) === selectedKey)

  // 기본 선택: 현재 소속과 일치하는 옵션이 있으면 자동 선택
  useEffect(() => {
    if (selectedKey || !options.length) return
    const current = options.find(
      (opt) =>
        opt.user_sdwt_prod === data?.currentUserSdwtProd &&
        opt.department === data?.currentDepartment &&
        opt.line === data?.currentLine,
    )
    if (current) {
      setSelectedKey(optionKey(current))
    }
  }, [selectedKey, options, data?.currentUserSdwtProd, data?.currentDepartment, data?.currentLine])

  const handleSubmit = (e) => {
    e.preventDefault()
    const target = selected || options.find((opt) => opt.user_sdwt_prod === data?.currentUserSdwtProd)
    if (!target) return
    const payload = {
      userSdwtProd: target.user_sdwt_prod,
      department: target.department,
      line: target.line,
      effectiveFrom: isoFromLocalInput(effectiveFrom),
    }
    onSubmit(payload, () => {
      setSelectedKey("")
      setEffectiveFrom("")
    })
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>My affiliation</CardTitle>
        <CardDescription>
          실제 변경된 user_sdwt_prod와 변경 시점을 입력하세요. 시간은 {timezoneName} 기준입니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 rounded-lg border p-3">
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">현재 user_sdwt_prod</span>
            <span className="text-lg font-semibold text-foreground">
              {data?.currentUserSdwtProd || "미지정"}
            </span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">현재 Department / Line</span>
            <span className="text-sm text-foreground">
              {(data?.currentDepartment || "미지정") + " / " + (data?.currentLine || "미지정")}
            </span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-3">
          <div className="grid gap-2">
            <Label htmlFor="affiliationSelect">변경할 소속 (Department / Line / user_sdwt_prod)</Label>
            <select
              id="affiliationSelect"
              className="bg-background border-input focus-visible:ring-ring/50 focus-visible:ring-[3px] h-10 rounded-md border px-3 text-sm outline-none"
              value={selectedKey}
              onChange={(e) => setSelectedKey(e.target.value)}
              required
              disabled={!options.length}
            >
              <option value="" disabled>
                소속을 선택하세요
              </option>
              {options.map((opt) => (
                <option key={optionKey(opt)} value={optionKey(opt)}>
                  {opt.department} / {opt.line} / {opt.user_sdwt_prod}
                </option>
              ))}
            </select>
            {!options.length ? (
              <p className="text-sm text-destructive">선택 가능한 소속이 없습니다. 관리자에게 문의하세요.</p>
            ) : null}
          </div>

          <div className="grid gap-2">
            <Label htmlFor="effectiveFrom">
              실제 변경 시점 (선택, {timezoneName})
            </Label>
            <Input
              id="effectiveFrom"
              type="datetime-local"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
            />
            <p className="text-sm text-muted-foreground">
              비워두면 지금 시점으로 적용됩니다. 과거 시점을 입력하면 그 이후 메일과 RAG가 새 소속으로 분류되도록 기록됩니다.
            </p>
          </div>

          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !options.length || !selectedKey}>
              {isSubmitting ? "저장 중..." : "변경 저장"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
