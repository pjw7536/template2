// src/app/api/line-dashboard/history/route.js
import { NextResponse } from "next/server"

import { runQuery } from "@/lib/db"
import { DEFAULT_TABLE } from "@/features/line-dashboard/components/data-table/utils/constants"
import { findColumn, pickBaseTimestampColumn } from "@/features/line-dashboard/api/columns"
import { buildLineFilters } from "@/features/line-dashboard/api/lineFilters"
import { normalizeDateOnly, sanitizeIdentifier } from "@/features/line-dashboard/api/validation"

const DIMENSION_CANDIDATES = [
  "sdwt",
  "user_sdwt",
  "eqp_id",
  "main_step",
  "sample_type",
  "line_id",
]

const DEFAULT_RANGE_DAYS = 14
const MS_IN_DAY = 86_400_000

function toDateString(value) {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) {
      return null
    }

    if (trimmed.length >= 10) {
      return trimmed.slice(0, 10)
    }

    return trimmed
  }

  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const year = value.getFullYear()
    const month = String(value.getMonth() + 1).padStart(2, "0")
    const day = String(value.getDate()).padStart(2, "0")
    return `${year}-${month}-${day}`
  }

  return null
}

function resolveDateRange(fromParam, toParam, rangeParam) {
  let from = fromParam ?? null
  let to = toParam ?? null

  const parsedRange = Number.parseInt(rangeParam ?? "", 10)
  const rangeDays = Number.isFinite(parsedRange) && parsedRange > 0 ? parsedRange : DEFAULT_RANGE_DAYS

  if (!to) {
    const now = new Date()
    const todayUtc = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
    to = toDateString(todayUtc)
  }

  if (!from && to) {
    const toDate = new Date(`${to}T00:00:00Z`)
    if (Number.isFinite(toDate.getTime())) {
      const fromDate = new Date(toDate.getTime() - (rangeDays - 1) * MS_IN_DAY)
      from = toDateString(fromDate)
    }
  }

  if (from && to) {
    const fromTime = Date.parse(`${from}T00:00:00Z`)
    const toTime = Date.parse(`${to}T00:00:00Z`)
    if (Number.isFinite(fromTime) && Number.isFinite(toTime) && fromTime > toTime) {
      ;[from, to] = [to, from]
    }
  }

  return { from, to }
}

function buildWhereClause(timestampColumn, lineFilters, lineParams, from, to) {
  const conditions = Array.isArray(lineFilters) ? [...lineFilters] : []
  const params = Array.isArray(lineParams) ? [...lineParams] : []

  if (from) {
    params.push(`${from} 00:00:00`)
    conditions.push(`\`${timestampColumn}\` >= ?`)
  }

  if (to) {
    params.push(`${to} 23:59:59`)
    conditions.push(`\`${timestampColumn}\` <= ?`)
  }

  return {
    clause: conditions.length ? `WHERE ${conditions.join(" AND ")}` : "",
    params,
  }
}

function normalizeDailyRow(row) {
  const rawDate = row?.day ?? row?.date
  const date = toDateString(rawDate)
  return {
    date,
    rowCount: Number.parseInt(row?.row_count ?? row?.rowCount ?? 0, 10) || 0,
    sendJiraCount: Number.parseInt(row?.send_jira_count ?? row?.sendJiraCount ?? 0, 10) || 0,
  }
}

function normalizeBreakdownRow(row) {
  const rawDate = row?.day ?? row?.date
  const date = toDateString(rawDate)
  const category = row?.category ?? row?.dimension ?? "Unspecified"

  return {
    date,
    category: typeof category === "string" && category.trim().length > 0 ? category.trim() : "Unspecified",
    rowCount: Number.parseInt(row?.row_count ?? row?.rowCount ?? 0, 10) || 0,
    sendJiraCount: Number.parseInt(row?.send_jira_count ?? row?.sendJiraCount ?? 0, 10) || 0,
  }
}

export async function GET(request) {
  const url = new URL(request.url)
  const searchParams = url.searchParams

  const tableParam = searchParams.get("table")
  const fromParam = normalizeDateOnly(searchParams.get("from"))
  const toParam = normalizeDateOnly(searchParams.get("to"))
  const lineIdParam = searchParams.get("lineId")
  const rangeParam = searchParams.get("rangeDays")

  const tableName = sanitizeIdentifier(tableParam, DEFAULT_TABLE)
  if (!tableName) {
    return NextResponse.json({ error: "Invalid table name" }, { status: 400 })
  }

  const normalizedLineId =
    typeof lineIdParam === "string" && lineIdParam.trim().length > 0 ? lineIdParam.trim() : null

  const { from, to } = resolveDateRange(fromParam, toParam, rangeParam)

  try {
    const columnRows = await runQuery(`SHOW COLUMNS FROM \`${tableName}\``)
    const columnNames = columnRows
      .map((column) => column?.Field)
      .filter((name) => typeof name === "string")

    if (columnNames.length === 0) {
      return NextResponse.json({ error: `Table "${tableName}" has no columns` }, { status: 400 })
    }

    const timestampColumn = pickBaseTimestampColumn(columnNames)
    if (!timestampColumn) {
      return NextResponse.json(
        { error: `No timestamp-like column found in "${tableName}".` },
        { status: 400 }
      )
    }

    const sendJiraColumn = findColumn(columnNames, "send_jira")
    const dimensionColumns = {}
    for (const candidate of DIMENSION_CANDIDATES) {
      const resolved = findColumn(columnNames, candidate)
      if (resolved) {
        dimensionColumns[candidate] = resolved
      }
    }

    const { filters: lineFilters, params: lineParams } = await buildLineFilters(columnNames, normalizedLineId)

    const { clause: whereClause, params } = buildWhereClause(
      timestampColumn,
      lineFilters,
      lineParams,
      from,
      to
    )

    const totalsSelect = [
      "DATE(\`" + timestampColumn + "\`) AS day",
      "COUNT(*) AS row_count",
    ]

    if (sendJiraColumn) {
      totalsSelect.push(
        `SUM(CASE WHEN \`${sendJiraColumn}\` IS NOT NULL AND \`${sendJiraColumn}\` <> 0 THEN 1 ELSE 0 END) AS send_jira_count`
      )
    } else {
      totalsSelect.push("0 AS send_jira_count")
    }

    const totalsQuery = `
      SELECT ${totalsSelect.join(",")}
      FROM \`${tableName}\`
      ${whereClause}
      GROUP BY day
      ORDER BY day ASC
    `

    const totalsRows = await runQuery(totalsQuery, params)
    const totals = totalsRows.map(normalizeDailyRow)

    const breakdowns = {}
    for (const [dimensionKey, columnName] of Object.entries(dimensionColumns)) {
      const breakdownSelect = [
        "DATE(\`" + timestampColumn + "\`) AS day",
        `COALESCE(CAST(\`${columnName}\` AS CHAR), 'Unspecified') AS category`,
        "COUNT(*) AS row_count",
      ]

      if (sendJiraColumn) {
        breakdownSelect.push(
          `SUM(CASE WHEN \`${sendJiraColumn}\` IS NOT NULL AND \`${sendJiraColumn}\` <> 0 THEN 1 ELSE 0 END) AS send_jira_count`
        )
      } else {
        breakdownSelect.push("0 AS send_jira_count")
      }

      const breakdownQuery = `
        SELECT ${breakdownSelect.join(",")}
        FROM \`${tableName}\`
        ${whereClause}
        GROUP BY day, category
        ORDER BY day ASC, category ASC
      `

      const rows = await runQuery(breakdownQuery, params)
      breakdowns[dimensionKey] = rows.map(normalizeBreakdownRow)
    }

    return NextResponse.json({
      table: tableName,
      from,
      to,
      lineId: normalizedLineId,
      timestampColumn,
      generatedAt: new Date().toISOString(),
      totals,
      breakdowns,
    })
  } catch (error) {
    console.error("Failed to load history data", error)
    return NextResponse.json({ error: "Failed to load history data" }, { status: 500 })
  }
}
