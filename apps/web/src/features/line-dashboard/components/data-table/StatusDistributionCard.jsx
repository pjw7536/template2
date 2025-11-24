// src/features/line-dashboard/components/data-table/StatusDistributionCard.jsx
import * as React from "react"
import { Label, Pie, PieChart, ResponsiveContainer } from "recharts"

import { ChartContainer } from "@/components/ui/chart"

import { numberFormatter } from "./utils/constants"

export function StatusDistributionCard({ data, config, total }) {
  const hasData = Array.isArray(data) && data.length > 0 && total > 0
  const [hoveredSlice, setHoveredSlice] = React.useState(null)

  React.useEffect(() => {
    setHoveredSlice(null)
  }, [data])

  const handleSliceHover = React.useCallback(
    (_slice, index) => {
      setHoveredSlice(data?.[index] ?? null)
    },
    [data]
  )

  const handleSliceLeave = React.useCallback(() => {
    setHoveredSlice(null)
  }, [])

  return (
    <div className="item-center">
      {hasData ? (
        <ChartContainer config={config} className="mx-auto h-[130px] w-full max-w-[130px]">
          <ResponsiveContainer width="100%" height="100%" >
            <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <Pie
                data={data}
                dataKey="value"
                nameKey="status"
                innerRadius="50%"
                strokeWidth={0}
                onMouseEnter={handleSliceHover}
                onMouseLeave={handleSliceLeave}
              >
                <Label
                  content={({ viewBox }) => {
                    if (!viewBox || typeof viewBox.cx !== "number" || typeof viewBox.cy !== "number") {
                      return null
                    }
                    const primaryText = hoveredSlice?.label ?? 'Total'
                    const secondaryText = hoveredSlice
                      ? `${numberFormatter.format(hoveredSlice.value)}`
                      : `${numberFormatter.format(total)}`
                    return (
                      <text
                        x={viewBox.cx}
                        y={viewBox.cy}
                        textAnchor="middle"
                        dominantBaseline="top"
                      >
                        <tspan
                          x={viewBox.cx}
                          y={viewBox.cy}
                          className="fill-foreground text-xs font-semibold"
                        >
                          {primaryText}
                        </tspan>
                        <tspan
                          x={viewBox.cx}
                          y={viewBox.cy + 12}
                          className="fill-muted-foreground text-xs"
                        >
                          {secondaryText}
                        </tspan>
                      </text>
                    )
                  }}
                />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </ChartContainer>
      ) : (
        <div className="flex h-[130px] w-[150px] items-center justify-center text-xs text-muted-foreground">
          현재 필터된 행이 없습니다.
        </div>
      )}
    </div>
  )
}
