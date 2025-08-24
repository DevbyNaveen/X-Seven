"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Clock, CheckCircle, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Order } from "@/app/dashboard/orders/page"

interface OrderGridProps {
  orders: Order[]
  onOrderClick: (order: Order) => void
}

const statusConfig = {
  preparing: {
    color: "bg-orange-500/10 border-orange-500/20 text-orange-700 dark:text-orange-300",
    icon: Clock,
    label: "Preparing",
  },
  ready: {
    color: "bg-blue-500/10 border-blue-500/20 text-blue-700 dark:text-blue-300",
    icon: CheckCircle,
    label: "Ready",
  },
  completed: {
    color: "bg-green-500/10 border-green-500/20 text-green-700 dark:text-green-300",
    icon: CheckCircle,
    label: "Completed",
  },
  cancelled: {
    color: "bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-300",
    icon: AlertCircle,
    label: "Cancelled",
  },
}

export function OrderGrid({ orders, onOrderClick }: OrderGridProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
      {orders.map((order) => {
        const config = statusConfig[order.status]
        const StatusIcon = config.icon

        return (
          <Card
            key={order.id}
            className={cn(
              "p-6 cursor-pointer transition-all duration-200 hover:scale-105 hover:shadow-lg",
              config.color,
              order.status === "ready" && "ring-2 ring-blue-500/50",
            )}
            onClick={() => onOrderClick(order)}
          >
            <div className="text-center space-y-3">
              {/* Order Number */}
              <div className="text-3xl font-heading font-bold">{order.orderNumber}</div>

              {/* Status Badge */}
              <Badge variant="secondary" className="text-xs">
                <StatusIcon className="h-3 w-3 mr-1" />
                {config.label}
              </Badge>

              {/* Customer Name */}
              <div className="text-sm font-medium truncate">{order.customer}</div>

              {/* Order Details */}
              <div className="text-xs text-muted-foreground space-y-1">
                <div>${order.total.toFixed(2)}</div>
                {order.estimatedTime && <div>{order.estimatedTime}</div>}
              </div>

              {/* Items Count */}
              <div className="text-xs text-muted-foreground">
                {order.items.reduce((sum, item) => sum + item.quantity, 0)} items
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
