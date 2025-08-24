"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface OrderTrendsChartProps {
  timeRange: string
}

const data = [
  { date: "Jan 1", orders: 45 },
  { date: "Jan 2", orders: 52 },
  { date: "Jan 3", orders: 48 },
  { date: "Jan 4", orders: 61 },
  { date: "Jan 5", orders: 55 },
  { date: "Jan 6", orders: 67 },
  { date: "Jan 7", orders: 72 },
  { date: "Jan 8", orders: 58 },
  { date: "Jan 9", orders: 63 },
  { date: "Jan 10", orders: 69 },
  { date: "Jan 11", orders: 74 },
  { date: "Jan 12", orders: 81 },
  { date: "Jan 13", orders: 76 },
  { date: "Jan 14", orders: 85 },
]

const chartConfig = {
  orders: {
    label: "Orders",
    color: "hsl(var(--chart-2))",
  },
}

export function OrderTrendsChart({ timeRange }: OrderTrendsChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Line
            type="monotone"
            dataKey="orders"
            stroke="var(--color-orders)"
            strokeWidth={2}
            dot={{ fill: "var(--color-orders)" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
