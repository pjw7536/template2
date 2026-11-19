/** CSV 업로드 해석과 검증입니다. 규칙은 deploy/keycloak/scripts/init_sdwt.py와 같습니다. */

/** 따옴표·쉼표·줄바꿈을 처리하는 최소 CSV 파서입니다. 빈 줄은 건너뜁니다. */
export function parseCsv(text) {
  const source = text.replace(/^\uFEFF/, "")
  const records = []
  let record = []
  let field = ""
  let quoted = false
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i]
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') {
        field += '"'
        i += 1
      } else if (char === '"') {
        quoted = false
      } else {
        field += char
      }
    } else if (char === '"') {
      quoted = true
    } else if (char === ",") {
      record.push(field)
      field = ""
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[i + 1] === "\n") i += 1
      record.push(field)
      if (record.some((value) => value !== "")) records.push(record)
      record = []
      field = ""
    } else {
      field += char
    }
  }
  record.push(field)
  if (record.some((value) => value !== "")) records.push(record)
  const [header = [], ...rows] = records
  return { header: header.map((name) => name.trim()), rows }
}

/** 소속 그룹 경로 한 단계로 쓸 수 있는 이름인지 확인합니다. ':'는 소속별 역할 이름(<SDWT>:<등급>)의 구분자라 쓸 수 없습니다. */
export function validGroupName(name) {
  return Boolean(name) && !/[/:]/.test(name) && name !== "." && name !== ".." && name === name.trim()
}

function readRows(text, required) {
  const { header, rows } = parseCsv(text)
  const missing = required.filter((name) => !header.includes(name))
  if (missing.length) return { error: `헤더에 ${missing.join(", ")}가 필요합니다.`, rows: [] }
  if (new Set(header).size !== header.length) return { error: "헤더에 중복된 열이 있습니다.", rows: [] }
  if (!rows.length) return { error: "데이터 행이 없습니다.", rows: [] }
  return {
    rows: rows.map((values, index) => ({
      number: index + 2,
      columns: values.length,
      value: Object.fromEntries(header.map((name, column) => [name, values[column] ?? ""])),
    })),
    width: header.length,
  }
}

/** 팀·라인·SDWT 목록 CSV(user_sdwt_prod,line_id,department)를 검증합니다. 오류가 하나라도 있으면 적용하지 않습니다. */
export function readSdwtCsv(text) {
  const { error, rows, width } = readRows(text, ["user_sdwt_prod", "line_id", "department"])
  if (error) return { items: [], errors: [error] }
  const errors = []
  const items = []
  const seen = new Set()
  for (const row of rows) {
    const sdwt = row.value.user_sdwt_prod
    const line = row.value.line_id
    const team = row.value.department
    if (row.columns !== width) errors.push(`${row.number}행: 열 수가 맞지 않습니다.`)
    else if (![sdwt, line, team].every(validGroupName)) errors.push(`${row.number}행: 빈 값, 앞뒤 공백, '/', ':'는 쓸 수 없습니다.`)
    else if (seen.has(sdwt)) errors.push(`${row.number}행: SDWT '${sdwt}'가 중복됩니다.`)
    else {
      seen.add(sdwt)
      items.push({ sdwt, line, team })
    }
  }
  return { items, errors }
}

/** 사용자 소속 CSV(userid,user_sdwt_prod)를 검증합니다. SDWT가 비어 있으면 소속 없음입니다. */
export function readUserCsv(text) {
  const { error, rows, width } = readRows(text, ["userid", "user_sdwt_prod"])
  if (error) return { items: [], errors: [error] }
  const errors = []
  const items = []
  const seen = new Set()
  for (const row of rows) {
    const userid = row.value.userid
    const sdwt = row.value.user_sdwt_prod
    if (row.columns !== width) errors.push(`${row.number}행: 열 수가 맞지 않습니다.`)
    else if (!userid || userid !== userid.trim() || sdwt !== sdwt.trim()) errors.push(`${row.number}행: EPID가 비었거나 앞뒤 공백이 있습니다.`)
    else if (seen.has(userid)) errors.push(`${row.number}행: EPID '${userid}'가 중복됩니다.`)
    else {
      seen.add(userid)
      items.push({ number: row.number, userid, sdwt })
    }
  }
  return { items, errors }
}
