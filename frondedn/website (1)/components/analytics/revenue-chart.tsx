"use client"

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface RevenueChartProps {
  timeRange: string
}

const data = [
  { month: "Jan", revenue: 4200 },
  { month: "Feb", revenue: 3800 },
  { month: "Mar", revenue: 5200 },
  { month: "Apr", revenue: 4800 },
  { month: "May", revenue: 6200 },
  { month: "Jun", revenue: 5800 },
  { month: "Jul", revenue: 7200 },
  { month: "Aug", revenue: 6800 },
  { month: "Sep", revenue: 5900 },
  { month: "Oct", revenue: 6400 },
  { month: "Nov", revenue: 7800 },
  { month: "Dec", revenue: 8200 },
]

const chartConfig = {
  revenue: {
    label: "Revenue",
    color: "hsl(var(--chart-1))",
  },
}

export function RevenueChart({ timeRange }: RevenueChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="revenue" fill="var(--color-revenue)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
