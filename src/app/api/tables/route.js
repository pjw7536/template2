import { NextResponse } from "next/server"
import { runQuery } from "@/lib/db"
import { DEFAULT_TABLE } from "@/features/line-dashboard/components/data-table/utils/constants"
import {
  DATE_COLUMN_CANDIDATES,
} from "@/features/line-dashboard/api/constants"
import {
  pickBaseTimestampColumn,
} from "@/features/line-dashboard/api/columns"
import {
  normalizeDateOnly,
  sanitizeIdentifier,
} from "@/features/line-dashboard/api/validation"
import { buildLineFilters } from "@/features/line-dashboard/api/lineFilters"

/**
 * GET /api/tables
 * ----------------
 * Provides a single entry point for fetching table data with consistent date
 * filtering semantics. The heavy lifting is delegated to small focused helper
 * modules so this handler can read like a high level recipe:
 *
 *  1. Validate incoming query parameters
 *  2. Inspect the table schema for a usable timestamp column
 *  3. Build WHERE clauses for the requested line and time range
 *  4. Execute the query and respond with JSON
 */
export async function GET(request) {
  const url = new URL(request.url)
  const searchParams = url.searchParams

  const tableParam = searchParams.get("table")
  const fromParam = searchParams.get("from")
  const toParam = searchParams.get("to")
  const lineIdParam = searchParams.get("lineId")

  const tableName = sanitizeIdentifier(tableParam, DEFAULT_TABLE)
  if (!tableName) {
    return NextResponse.json({ error: "Invalid table name" }, { status: 400 })
  }

  let normalizedFrom = normalizeDateOnly(fromParam)
  let normalizedTo = normalizeDateOnly(toParam)

  if (normalizedFrom && normalizedTo) {
    const fromMs = Date.parse(`${normalizedFrom}T00:00:00Z`)
    const toMs = Date.parse(`${normalizedTo}T23:59:59Z`)
    if (Number.isFinite(fromMs) && Number.isFinite(toMs) && fromMs > toMs) {
      ;[normalizedFrom, normalizedTo] = [normalizedTo, normalizedFrom]
    }
  }

  const normalizedLineId =
    typeof lineIdParam === "string" && lineIdParam.trim().length > 0
      ? lineIdParam.trim()
      : null

  try {
    const columnRows = await runQuery(`SHOW COLUMNS FROM \`${tableName}\``)
    const columnNames = columnRows
      .map((column) => column?.Field)
      .filter((name) => typeof name === "string")

    if (columnNames.length === 0) {
      return NextResponse.json({ error: `Table "${tableName}" has no columns` }, { status: 400 })
    }

    const baseTsCol = pickBaseTimestampColumn(columnNames)
    if (!baseTsCol) {
      return NextResponse.json(
        {
          error:
            `No timestamp-like column found in "${tableName}". ` +
            `Expected one of: ${DATE_COLUMN_CANDIDATES.join(", ")}.`,
        },
        { status: 400 }
      )
    }

    const { filters: lineFilters, params: lineParams, earlyEmpty } = await buildLineFilters(
      columnNames,
      normalizedLineId
    )

    if (earlyEmpty) {
      return NextResponse.json({
        table: tableName,
        cutoff: `${baseTsCol} >= CONVERT_TZ(UTC_TIMESTAMP(),'UTC','+09:00') - INTERVAL 36 HOUR`,
        from: null,
        to: null,
        rowCount: 0,
        columns: columnNames,
        rows: [],
      })
    }

    const whereParts = [...lineFilters]
    const params = [...lineParams]

    whereParts.push(`\`${baseTsCol}\` >= (CONVERT_TZ(UTC_TIMESTAMP(), 'UTC', '+09:00') - INTERVAL 36 HOUR)`)

    if (normalizedFrom) {
      params.push(`${normalizedFrom} 00:00:00`)
      whereParts.push(`\`${baseTsCol}\` >= ?`)
    }

    if (normalizedTo) {
      params.push(`${normalizedTo} 23:59:59`)
      whereParts.push(`\`${baseTsCol}\` <= ?`)
    }

    const whereClause = whereParts.length ? `WHERE ${whereParts.join(" AND ")}` : ""
    const orderClause = `ORDER BY \`${baseTsCol}\` DESC, \`id\` DESC`

    const rows = await runQuery(
      `
        SELECT *
        FROM \`${tableName}\`
        ${whereClause}
        ${orderClause}
      `,
      params
    )

    return NextResponse.json({
      table: tableName,
      cutoff: `${baseTsCol} >= CONVERT_TZ(UTC_TIMESTAMP(),'UTC','+09:00') - INTERVAL 36 HOUR`,
      from: normalizedFrom || null,
      to: normalizedTo || null,
      rowCount: rows.length,
      columns: columnNames,
      rows,
    })
  } catch (error) {
    if (error && typeof error === "object" && error.code === "ER_NO_SUCH_TABLE") {
      return NextResponse.json({ error: `Table "${tableName}" was not found` }, { status: 404 })
    }

    console.error("Failed to load table data", error)
    return NextResponse.json({ error: "Failed to load table data" }, { status: 500 })
  }
}
