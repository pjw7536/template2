import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"

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
    }
    onSubmit(payload, () => {
      setSelectedKey("")
    })
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <CardTitle>My affiliation</CardTitle>
        <CardDescription>
          소속 변경을 신청하면 해당 소속 관리자 또는 슈퍼유저가 승인할 수 있습니다. 적용 시점은 승인 시점으로 고정됩니다.
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

          <p className="text-sm text-muted-foreground">
            실제 이동 날짜를 기준으로 메일/RAG 인덱스를 재분류하는 작업은 시스템 운영자 권한으로만 처리됩니다.
          </p>

          {error ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !options.length || !selectedKey}>
              {isSubmitting ? "요청 중..." : "변경 신청"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
