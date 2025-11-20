// src/components/ui/slider.jsx
import * as React from "react"

import { cn } from "@/lib/utils"

const clamp = (value, min, max) => {
  if (!Number.isFinite(value)) return min
  return Math.min(Math.max(value, min), max)
}

const Slider = React.forwardRef(
  (
    {
      className,
      value = [],
      min = 0,
      max = 100,
      step = 1,
      onValueChange,
      onValueCommit,
      ...props
    },
    ref
  ) => {
    const numericMin = Number.isFinite(min) ? min : 0
    const numericMax = Number.isFinite(max) ? max : 100
    const rawValue = Array.isArray(value) ? value[0] : value
    const clampedValue = clamp(Number(rawValue), numericMin, numericMax)
    const percentage =
      numericMax === numericMin
        ? 0
        : clamp(((clampedValue - numericMin) / (numericMax - numericMin)) * 100, 0, 100)

    const emitChange = React.useCallback(
      (next) => {
        if (typeof onValueChange === "function") {
          onValueChange([next])
        }
      },
      [onValueChange]
    )

    const emitCommit = React.useCallback(
      (next) => {
        if (typeof onValueCommit === "function") {
          onValueCommit([next])
        }
      },
      [onValueCommit]
    )

    const handleChange = (event) => {
      const next = Number(event.target.value)
      emitChange(clamp(next, numericMin, numericMax))
    }

    const handleCommit = (event) => {
      const next = Number(event.target.value)
      emitCommit(clamp(next, numericMin, numericMax))
    }

    return (
      <div className={cn("relative flex w-full items-center", className)}>
        <div className="relative w-full">
          <div className="h-1.5 rounded-full bg-muted" />
          <div
            className="absolute inset-y-0 left-0 h-1.5 rounded-full bg-primary"
            style={{ width: `${percentage}%` }}
          />
          <div
            className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/40 bg-background shadow ring-offset-background transition-[box-shadow,transform]"
            style={{ left: `${percentage}%` }}
          />
          <input
            ref={ref}
            type="range"
            min={numericMin}
            max={numericMax}
            step={step}
            value={clampedValue}
            onChange={handleChange}
            onMouseUp={handleCommit}
            onTouchEnd={handleCommit}
            onKeyUp={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                handleCommit(event)
              }
            }}
            className="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-transparent opacity-0"
            {...props}
          />
        </div>
      </div>
    )
  }
)
Slider.displayName = "Slider"

export { Slider }
