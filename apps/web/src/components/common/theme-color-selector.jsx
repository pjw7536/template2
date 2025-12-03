// src/components/common/theme-color-selector.jsx
import { Palette, Check } from "lucide-react"

import { Button } from "components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "components/ui/dropdown-menu"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

const COLOR_OPTIONS = [
  { value: "violet", label: "Violet", iconClass: "text-violet-500" },
  { value: "emerald", label: "Emerald", iconClass: "text-emerald-500" },
  { value: "amber", label: "Amber", iconClass: "text-amber-500" },
  { value: "sky", label: "Sky", iconClass: "text-sky-500" },
  { value: "rose", label: "Rose", iconClass: "text-rose-500" },
]

export function ThemeColorSelector({ className }) {
  const { colorScheme, setColorScheme } = useTheme()
  const activeOption =
    COLOR_OPTIONS.find((option) => option.value === colorScheme) ??
    COLOR_OPTIONS[0]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {/* ▶ ThemeToggle과 동일하게 border 없는 ghost 아이콘 버튼 */}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Select accent color"
          className={cn("transition-all", className)}
        >
          <Palette
            className={cn(
              "size-4 transition-colors",
              activeOption.iconClass // 선택된 색으로 아이콘 컬러 변환
            )}
          />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-40" align="end">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Accent color
        </DropdownMenuLabel>

        {COLOR_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            className="flex items-center gap-2"
            onSelect={() => setColorScheme(option.value)}
          >
            <Palette
              className={cn("size-4", option.iconClass)}
            />
            <span className="flex-1 text-sm">{option.label}</span>

            {option.value === colorScheme && (
              <Check className="size-3.5" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
