"use client"

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface TopProductsChartProps {
  timeRange: string
}

const data = [
  { product: "Burger Deluxe", sales: 245, revenue: 3675 },
  { product: "Pizza Margherita", sales: 189, revenue: 3591 },
  { product: "Caesar Salad", sales: 156, revenue: 2028 },
  { product: "Fish & Chips", sales: 134, revenue: 2276 },
  { product: "Pasta Carbonara", sales: 98, revenue: 1470 },
]

const chartConfig = {
  sales: {
    label: "Sales",
    color: "hsl(var(--chart-1))",
  },
  revenue: {
    label: "Revenue",
    color: "hsl(var(--chart-2))",
  },
}

export function TopProductsChart({ timeRange }: TopProductsChartProps) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="horizontal">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis dataKey="product" type="category" width={100} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="sales" fill="var(--color-sales)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
