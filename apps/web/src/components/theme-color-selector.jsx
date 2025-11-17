// src/components/theme-color-selector.jsx
// 다크모드 스위치 왼쪽에 배치하는 포인트 컬러 선택 드롭다운

import { Palette, Check } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

const COLOR_OPTIONS = [
  { value: "violet", label: "Violet", dotClass: "bg-violet-500" },
  { value: "emerald", label: "Emerald", dotClass: "bg-emerald-500" },
  { value: "amber", label: "Amber", dotClass: "bg-amber-500" },
  { value: "sky", label: "Sky", dotClass: "bg-sky-500" },
  { value: "rose", label: "Rose", dotClass: "bg-rose-500" },
]

export function ThemeColorSelector({ className }) {
  const { colorScheme, setColorScheme } = useTheme()
  const activeOption = COLOR_OPTIONS.find((option) => option.value === colorScheme) ?? COLOR_OPTIONS[0]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          aria-label="Select accent color"
          className={cn("gap-2", className)}
        >
          <span className="flex items-center gap-1.5">
            <Palette className="size-3.5 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">Theme</span>
          </span>
          <span
            className={cn("size-3 rounded-full border border-border", activeOption.dotClass)}
            aria-hidden="true"
          />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-40" align="end">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Accent color</DropdownMenuLabel>
        {COLOR_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            className="flex items-center gap-2"
            onSelect={() => {
              setColorScheme(option.value)
            }}
          >
            <span
              className={cn(
                "size-4 rounded-full border border-border transition-colors",
                option.dotClass
              )}
              aria-hidden="true"
            />
            <span className="flex-1 text-sm">{option.label}</span>
            {option.value === colorScheme ? <Check className="size-3.5" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
