import * as React from "react"
import { useParams } from "react-router-dom"

const ActiveLineContext = React.createContext(null)

function normalizeLineId(value) {
  if (value === null || value === undefined) return null
  return typeof value === "string" ? value : String(value)
}

function getLineIdFromParams(params) {
  if (!params || typeof params !== "object") return null
  const raw = params.lineId
  if (typeof raw === "string") return raw
  if (Array.isArray(raw)) return raw[0] ?? null
  return null
}

function normalizeLineOptionIds(lineOptions) {
  if (!Array.isArray(lineOptions)) return []
  return lineOptions
    .map((option) => {
      if (!option) return null
      if (typeof option === "string" || typeof option === "number") {
        return normalizeLineId(option)
      }
      if (option && option.id !== undefined && option.id !== null) {
        return normalizeLineId(option.id)
      }
      return null
    })
    .filter((id) => id !== null)
}

export function ActiveLineProvider({ children, lineOptions }) {
  const params = useParams()
  const paramLineId = normalizeLineId(getLineIdFromParams(params))

  const availableLineIds = normalizeLineOptionIds(lineOptions)
  const fallbackLineId = availableLineIds[0] ?? null

  const [selectedLineId, setSelectedLineId] = React.useState(
    () => paramLineId ?? fallbackLineId,
  )

  React.useEffect(() => {
    if (paramLineId && paramLineId !== selectedLineId) {
      setSelectedLineId(paramLineId)
    }
  }, [paramLineId, selectedLineId])

  React.useEffect(() => {
    if (!paramLineId && !selectedLineId && fallbackLineId) {
      setSelectedLineId(fallbackLineId)
    }
  }, [fallbackLineId, paramLineId, selectedLineId])

  React.useEffect(() => {
    if (!availableLineIds.length) return
    const hasSelectedLine =
      selectedLineId && availableLineIds.includes(selectedLineId)

    if (!hasSelectedLine) {
      const nextLineId =
        (paramLineId && availableLineIds.includes(paramLineId) ? paramLineId : null) ??
        fallbackLineId

      if (nextLineId !== selectedLineId) {
        setSelectedLineId(nextLineId ?? null)
      }
    }
  }, [availableLineIds, fallbackLineId, paramLineId, selectedLineId])

  const setLineId = (nextLineId) => {
    setSelectedLineId(normalizeLineId(nextLineId))
  }

  return (
    <ActiveLineContext.Provider value={{ lineId: selectedLineId ?? null, setLineId }}>
      {children}
    </ActiveLineContext.Provider>
  )
}

export function useActiveLine() {
  const context = React.useContext(ActiveLineContext)
  if (!context) {
    throw new Error("useActiveLine must be used within an ActiveLineProvider")
  }
  return context
}

export function useActiveLineOptional() {
  return React.useContext(ActiveLineContext)
}
