"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface CustomerRetentionChartProps {
  timeRange: string
}

const data = [
  { month: "Jan", retention: 85 },
  { month: "Feb", retention: 82 },
  { month: "Mar", retention: 88 },
  { month: "Apr", retention: 86 },
  { month: "May", retention: 90 },
  { month: "Jun", retention: 87 },
  { month: "Jul", retention: 92 },
  { month: "Aug", retention: 89 },
  { month: "Sep", retention: 91 },
  { month: "Oct", retention: 88 },
  { month: "Nov", retention: 94 },
  { month: "Dec", retention: 93 },
]

const chartConfig = {
  retention: {
    label: "Retention Rate",
    color: "hsl(var(--chart-3))",
  },
}

export function CustomerRetentionChart({ timeRange }: CustomerRetentionChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis domain={[75, 100]} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Line
            type="monotone"
            dataKey="retention"
            stroke="var(--color-retention)"
            strokeWidth={3}
            dot={{ fill: "var(--color-retention)", strokeWidth: 2, r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
