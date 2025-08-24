"use client"

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface SalesChartProps {
  timeRange: string
}

const data = [
  { time: "00:00", sales: 0 },
  { time: "02:00", sales: 12 },
  { time: "04:00", sales: 8 },
  { time: "06:00", sales: 45 },
  { time: "08:00", sales: 120 },
  { time: "10:00", sales: 180 },
  { time: "12:00", sales: 320 },
  { time: "14:00", sales: 280 },
  { time: "16:00", sales: 240 },
  { time: "18:00", sales: 380 },
  { time: "20:00", sales: 420 },
  { time: "22:00", sales: 180 },
]

const chartConfig = {
  sales: {
    label: "Sales",
    color: "hsl(var(--chart-1))",
  },
}

export function SalesChart({ timeRange }: SalesChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Area
            type="monotone"
            dataKey="sales"
            stroke="var(--color-sales)"
            fill="var(--color-sales)"
            fillOpacity={0.3}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
