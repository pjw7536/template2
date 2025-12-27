import { useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

function normalizeValue(value) {
  return typeof value === "string" ? value.trim() : ""
}

function normalizeValues(values) {
  if (!Array.isArray(values)) return []
  const normalized = values
    .map((value) => normalizeValue(value))
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

function splitInput(value) {
  if (!value) return []
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function TagInput({
  label,
  values,
  onChange,
  placeholder,
  helperText,
  suggestions = [],
  isDisabled = false,
}) {
  const [draft, setDraft] = useState("")
  const normalizedValues = useMemo(() => normalizeValues(values), [values])
  const normalizedSuggestions = useMemo(() => normalizeValues(suggestions), [suggestions])

  const addTags = (raw) => {
    const nextTags = splitInput(raw)
    if (nextTags.length === 0) return
    const merged = normalizeValues([...normalizedValues, ...nextTags])
    onChange(merged)
    setDraft("")
  }

  const removeTag = (value) => {
    const next = normalizedValues.filter((item) => item !== value)
    onChange(next)
  }

  const handleKeyDown = (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault()
      addTags(draft)
    }
  }

  const handleBlur = () => {
    if (!draft.trim()) return
    addTags(draft)
  }

  const availableSuggestions = normalizedSuggestions.filter(
    (value) => !normalizedValues.includes(value),
  )

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        {helperText ? (
          <span className="text-[11px] text-muted-foreground">{helperText}</span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-background px-2 py-2">
        {normalizedValues.map((value) => (
          <Badge key={value} variant="secondary" className="flex items-center gap-1 px-2 py-0.5 text-xs">
            <span>{value}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-4 w-4 text-muted-foreground hover:text-foreground"
              onClick={() => removeTag(value)}
              aria-label={`Remove ${value}`}
              disabled={isDisabled}
            >
              x
            </Button>
          </Badge>
        ))}
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          placeholder={placeholder}
          className="h-7 w-28 border-0 bg-transparent px-1 text-xs shadow-none focus-visible:ring-0"
          disabled={isDisabled}
        />
      </div>
      {availableSuggestions.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {availableSuggestions.map((value) => (
            <Button
              key={value}
              type="button"
              variant="outline"
              size="sm"
              className="h-6 px-2 text-[11px]"
              onClick={() => addTags(value)}
              disabled={isDisabled}
            >
              {value}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
