import { NativeSelect } from "./NativeSelect"
import { cn } from "@/lib/utils"

/**
 * 팀 → 라인 → SDWT를 차례로 고르는 선택 상자 묶음입니다.
 * value: { team, line, sdwt } (빈 문자열이면 선택 안 함)
 * depth: "team" | "line" | "sdwt" — 어디까지 고를지
 * placeholders: 각 상자의 첫 항목 문구. 팀 첫 항목은 "소속 없음"처럼 빈 선택의 뜻을 바꿀 때 씁니다.
 * fixedTeam: 화면에서 이미 팀을 골랐으면 팀 상자를 숨기고 이 팀 안에서만 고릅니다.
 */
export function OrgPicker({ org, value, onChange, depth = "sdwt", placeholders = {}, className, disabled, fixedTeam }) {
  const team = org.teams.find((item) => item.name === (fixedTeam ?? value.team))
  const line = team?.lines.find((item) => item.name === value.line)
  const labels = { team: "팀 선택", line: "라인 선택", sdwt: "SDWT 선택", ...placeholders }

  return (
    <div className={cn("flex min-w-0 flex-1 gap-2", className)}>
      {fixedTeam === undefined ? (
        <NativeSelect className="min-w-0 flex-1" aria-label="팀" value={value.team} disabled={disabled}
          onChange={(event) => onChange({ team: event.target.value, line: "", sdwt: "" })}>
          <option value="">{labels.team}</option>
          {org.teams.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
        </NativeSelect>
      ) : null}
      {depth !== "team" ? (
        <NativeSelect className="min-w-0 flex-1" aria-label="라인" value={value.line} disabled={disabled || !team}
          onChange={(event) => onChange({ ...value, team: team.name, line: event.target.value, sdwt: "" })}>
          <option value="">{labels.line}</option>
          {(team?.lines ?? []).map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
        </NativeSelect>
      ) : null}
      {depth === "sdwt" ? (
        <NativeSelect className="min-w-0 flex-1" aria-label="SDWT" value={value.sdwt} disabled={disabled || !line}
          onChange={(event) => onChange({ ...value, sdwt: event.target.value })}>
          <option value="">{labels.sdwt}</option>
          {(line?.sdwts ?? []).map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
        </NativeSelect>
      ) : null}
    </div>
  )
}

export const EMPTY_PICK = { team: "", line: "", sdwt: "" }

/** SDWT 이름으로 { team, line, sdwt } 선택값을 만듭니다. */
export function pickOf(org, sdwtName) {
  const sdwt = org.sdwts.get(sdwtName)
  return sdwt ? { team: sdwt.team, line: sdwt.line, sdwt: sdwt.name } : EMPTY_PICK
}
