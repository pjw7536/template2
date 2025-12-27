import { ChevronDown } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function normalizeList(values) {
  if (!Array.isArray(values)) return []
  const normalized = values
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter(Boolean)
  return Array.from(new Set(normalized))
}

export function RagIndexMultiSelect({
  label,
  values,
  options,
  onChange,
  helperText,
  placeholder = "선택하세요",
  isDisabled = false,
}) {
  const normalizedValues = normalizeList(values)
  const normalizedOptions = normalizeList(options)
  const hasSelection = normalizedValues.length > 0
  const canDeselect = normalizedValues.length > 1

  const handleCheckedChange = (value, checked) => {
    const isChecked = checked === true
    if (isChecked) {
      if (!normalizedValues.includes(value)) {
        onChange([...normalizedValues, value])
      }
      return
    }
    if (!canDeselect) return
    onChange(normalizedValues.filter((item) => item !== value))
  }

  const handleItemSelect = (event) => {
    event.preventDefault()
  }

  const selectionLabel = hasSelection ? normalizedValues.join(", ") : placeholder

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        {helperText ? (
          <span className="text-[11px] text-muted-foreground">{helperText}</span>
        ) : null}
      </div>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className="h-9 w-full justify-between text-xs"
            disabled={isDisabled || normalizedOptions.length === 0}
          >
            <span className={hasSelection ? "truncate" : "truncate text-muted-foreground"}>
              {selectionLabel}
            </span>
            <ChevronDown className="h-4 w-4 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="w-[var(--radix-dropdown-menu-trigger-width)]"
          data-chat-widget-portal="true"
        >
          {normalizedOptions.length ? (
            normalizedOptions.map((value) => {
              const isChecked = normalizedValues.includes(value)
              return (
                <DropdownMenuCheckboxItem
                  key={value}
                  checked={isChecked}
                  onSelect={handleItemSelect}
                  onCheckedChange={(checked) => handleCheckedChange(value, checked)}
                  disabled={isDisabled || (isChecked && !canDeselect)}
                >
                  {value}
                </DropdownMenuCheckboxItem>
              )
            })
          ) : (
            <DropdownMenuItem disabled>옵션 없음</DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {hasSelection ? (
        <div className="flex flex-wrap gap-1">
          {normalizedValues.map((value) => (
            <Badge key={value} variant="secondary" className="text-[11px]">
              {value}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  )
}
