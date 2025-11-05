// src/app/api/drone-early-inform/route.js
import { NextResponse } from "next/server"

import { getPool, runQuery } from "@/lib/db"

const TABLE_NAME = "drone_early_inform_v3"
const MAX_FIELD_LENGTH = 50

function sanitizeLineId(value) {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  if (trimmed.length === 0) return null
  if (trimmed.length > MAX_FIELD_LENGTH) return null
  return trimmed
}

function sanitizeMainStep(value) {
  if (typeof value !== "string") value = value === null || value === undefined ? "" : String(value)
  const trimmed = value.trim()
  if (trimmed.length === 0) return null
  if (trimmed.length > MAX_FIELD_LENGTH) return null
  return trimmed
}

function normalizeCustomEndStep(value) {
  if (value === undefined) {
    return { hasValue: false, value: null }
  }
  if (value === null) {
    return { hasValue: true, value: null }
  }
  const stringified = typeof value === "string" ? value : String(value)
  const trimmed = stringified.trim()
  if (trimmed.length === 0) {
    return { hasValue: true, value: null }
  }
  if (trimmed.length > MAX_FIELD_LENGTH) {
    throw new Error("customEndStep must be 50 characters or fewer")
  }
  return { hasValue: true, value: trimmed }
}

function mapRow(row) {
  if (!row || typeof row !== "object") return null
  const { id, line_id: lineId, main_step: mainStep, custom_end_step: customEndStep } = row
  if (id === null || id === undefined) return null
  return {
    id: Number(id),
    lineId: typeof lineId === "string" ? lineId : null,
    mainStep: typeof mainStep === "string" ? mainStep : mainStep === null || mainStep === undefined ? "" : String(mainStep),
    customEndStep:
      customEndStep === null || customEndStep === undefined
        ? null
        : typeof customEndStep === "string"
          ? customEndStep
          : String(customEndStep),
  }
}

function toJsonError(message, status = 400) {
  return NextResponse.json({ error: message }, { status })
}

export async function GET(request) {
  const url = new URL(request.url)
  const rawLineId = url.searchParams.get("lineId")
  const lineId = sanitizeLineId(rawLineId)

  if (!lineId) {
    return toJsonError("lineId is required", 400)
  }

  try {
    const rows = await runQuery(
      `
        SELECT id, line_id, main_step, custom_end_step
        FROM \`${TABLE_NAME}\`
        WHERE line_id = ?
        ORDER BY main_step ASC, id ASC
      `,
      [lineId]
    )

    const normalized = rows
      .map(mapRow)
      .filter((row) => row !== null)
      .map((row) => ({
        ...row,
        lineId: row.lineId ?? lineId,
      }))

    return NextResponse.json({
      lineId,
      rowCount: normalized.length,
      rows: normalized,
    })
  } catch (error) {
    console.error("Failed to load drone_early_inform_v3 rows", error)
    return toJsonError("Failed to load settings", 500)
  }
}

export async function POST(request) {
  let payload
  try {
    payload = await request.json()
  } catch {
    return toJsonError("Invalid JSON body", 400)
  }

  const lineId = sanitizeLineId(payload?.lineId)
  const mainStep = sanitizeMainStep(payload?.mainStep)

  if (!lineId) {
    return toJsonError("lineId is required", 400)
  }
  if (!mainStep) {
    return toJsonError("mainStep is required", 400)
  }

  let customEndStep
  try {
    customEndStep = normalizeCustomEndStep(payload?.customEndStep).value
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid customEndStep"
    return toJsonError(message, 400)
  }

  try {
    const pool = getPool()
    const [result] = await pool.execute(
      `
        INSERT INTO \`${TABLE_NAME}\` (line_id, main_step, custom_end_step)
        VALUES (?, ?, ?)
      `,
      [lineId, mainStep, customEndStep]
    )

    const entry = {
      id: Number(result?.insertId ?? 0),
      lineId,
      mainStep,
      customEndStep,
    }

    return NextResponse.json({ entry }, { status: 201 })
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ER_DUP_ENTRY") {
      return toJsonError("An entry for this main step already exists", 409)
    }

    console.error("Failed to insert drone_early_inform_v3 row", error)
    return toJsonError("Failed to create entry", 500)
  }
}

export async function PATCH(request) {
  let payload
  try {
    payload = await request.json()
  } catch {
    return toJsonError("Invalid JSON body", 400)
  }

  const rawId = payload?.id
  const idNumber = Number.parseInt(rawId, 10)
  if (!Number.isFinite(idNumber) || idNumber <= 0) {
    return toJsonError("A valid id is required", 400)
  }

  const updates = []
  const params = []

  if (Object.prototype.hasOwnProperty.call(payload, "mainStep")) {
    const nextMainStep = sanitizeMainStep(payload?.mainStep)
    if (!nextMainStep) {
      return toJsonError("mainStep is required", 400)
    }
    updates.push("`main_step` = ?")
    params.push(nextMainStep)
  }

  if (Object.prototype.hasOwnProperty.call(payload, "customEndStep")) {
    let normalized
    try {
      normalized = normalizeCustomEndStep(payload?.customEndStep)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid customEndStep"
      return toJsonError(message, 400)
    }
    if (normalized.hasValue) {
      updates.push("`custom_end_step` = ?")
      params.push(normalized.value)
    }
  }

  if (updates.length === 0) {
    return toJsonError("No valid fields to update", 400)
  }

  params.push(idNumber)

  try {
    const pool = getPool()
    const [result] = await pool.execute(
      `
        UPDATE \`${TABLE_NAME}\`
        SET ${updates.join(", ")}
        WHERE id = ?
        LIMIT 1
      `,
      params
    )

    if (!result || result.affectedRows === 0) {
      return toJsonError("Entry not found", 404)
    }

    const rows = await runQuery(
      `
        SELECT id, line_id, main_step, custom_end_step
        FROM \`${TABLE_NAME}\`
        WHERE id = ?
        LIMIT 1
      `,
      [idNumber]
    )

    const entry = mapRow(rows[0])
    if (!entry) {
      return toJsonError("Entry not found", 404)
    }

    return NextResponse.json({ entry })
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ER_DUP_ENTRY") {
      return toJsonError("An entry for this main step already exists", 409)
    }

    console.error("Failed to update drone_early_inform_v3 row", error)
    return toJsonError("Failed to update entry", 500)
  }
}

export async function DELETE(request) {
  const url = new URL(request.url)
  const rawId = url.searchParams.get("id")
  const idNumber = Number.parseInt(rawId ?? "", 10)

  if (!Number.isFinite(idNumber) || idNumber <= 0) {
    return toJsonError("A valid id is required", 400)
  }

  try {
    const pool = getPool()
    const [result] = await pool.execute(
      `
        DELETE FROM \`${TABLE_NAME}\`
        WHERE id = ?
        LIMIT 1
      `,
      [idNumber]
    )

    if (!result || result.affectedRows === 0) {
      return toJsonError("Entry not found", 404)
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Failed to delete drone_early_inform_v3 row", error)
    return toJsonError("Failed to delete entry", 500)
  }
}
