"use client"

import { PieChart, Pie, Cell, ResponsiveContainer, Legend } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface CustomerInsightsChartProps {
  timeRange: string
}

const data = [
  { name: "New Customers", value: 35, color: "hsl(var(--chart-1))" },
  { name: "Returning Customers", value: 45, color: "hsl(var(--chart-2))" },
  { name: "VIP Customers", value: 20, color: "hsl(var(--chart-3))" },
]

const chartConfig = {
  new: {
    label: "New Customers",
    color: "hsl(var(--chart-1))",
  },
  returning: {
    label: "Returning Customers",
    color: "hsl(var(--chart-2))",
  },
  vip: {
    label: "VIP Customers",
    color: "hsl(var(--chart-3))",
  },
}

export function CustomerInsightsChart({ timeRange }: CustomerInsightsChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value">
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <ChartTooltip content={<ChartTooltipContent />} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
