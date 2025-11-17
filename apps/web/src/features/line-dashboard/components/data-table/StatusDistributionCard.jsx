// src/features/line-dashboard/components/data-table/StatusDistributionCard.jsx
import { Label, Pie, PieChart, ResponsiveContainer } from "recharts"

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

import { numberFormatter } from "./utils/constants"

export function StatusDistributionCard({ data, config, total }) {
  const hasData = Array.isArray(data) && data.length > 0 && total > 0

  return (
    <div className="item-center">
      {hasData ? (
        <ChartContainer config={config} className="mx-auto h-[130px] w-full max-w-[130px]">
          <ResponsiveContainer width="100%" height="100%" >
            <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent hideLabel />}
              />
              <Pie
                data={data}
                dataKey="value"
                nameKey="status"
                innerRadius="50%"
                strokeWidth={0}
              >
                <Label
                  content={({ viewBox }) => {
                    if (!viewBox || typeof viewBox.cx !== "number" || typeof viewBox.cy !== "number") {
                      return null
                    }
                    return (
                      <text
                        x={viewBox.cx}
                        y={viewBox.cy}
                        textAnchor="middle"
                        dominantBaseline="middle"
                      >
                        <tspan
                          x={viewBox.cx}
                          y={viewBox.cy}
                          className="fill-foreground text-xl font-semibold"
                        >
                          {numberFormatter.format(total)}
                        </tspan>
                        <tspan
                          x={viewBox.cx}
                          y={viewBox.cy + 18}
                          className="fill-muted-foreground text-xs"
                        >
                          rows
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
        <div className="flex h-[150px] w-[150px] items-center justify-center text-xs text-muted-foreground">
          현재 필터된 행이 없습니다.
        </div>
      )}
    </div>
  )
}
