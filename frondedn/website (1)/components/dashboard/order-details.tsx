"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { X, Clock, User, DollarSign, FileText, Phone, MessageSquare } from "lucide-react"
import type { Order, OrderStatus } from "@/app/dashboard/orders/page"

interface OrderDetailsProps {
  order: Order
  onClose: () => void
  onStatusUpdate: (orderId: string, status: OrderStatus) => void
}

const statusActions = {
  preparing: [
    { status: "ready" as OrderStatus, label: "Mark Ready", variant: "default" as const },
    { status: "cancelled" as OrderStatus, label: "Cancel", variant: "destructive" as const },
  ],
  ready: [
    { status: "completed" as OrderStatus, label: "Complete", variant: "default" as const },
    { status: "preparing" as OrderStatus, label: "Back to Kitchen", variant: "outline" as const },
  ],
  completed: [],
  cancelled: [{ status: "preparing" as OrderStatus, label: "Reopen", variant: "outline" as const }],
}

export function OrderDetails({ order, onClose, onStatusUpdate }: OrderDetailsProps) {
  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const actions = statusActions[order.status]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-heading font-semibold">Order #{order.orderNumber}</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Status & Time */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Order Status</CardTitle>
                <Badge
                  variant={
                    order.status === "ready" ? "default" : order.status === "completed" ? "secondary" : "outline"
                  }
                >
                  {order.status.charAt(0).toUpperCase() + order.status.slice(1)}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span>Ordered at {formatTime(order.createdAt)}</span>
              </div>
              {order.estimatedTime && (
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span>Est. completion: {order.estimatedTime}</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Customer Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Customer</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{order.customer}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Phone className="h-4 w-4 mr-2" />
                  Call
                </Button>
                <Button variant="outline" size="sm">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Chat
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Order Items */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Items</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {order.items.map((item, index) => (
                  <div key={index}>
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{item.quantity}x</span>
                          <span>{item.name}</span>
                        </div>
                        {item.notes && <p className="text-sm text-muted-foreground mt-1">{item.notes}</p>}
                      </div>
                      <span className="font-medium">${(item.price * item.quantity).toFixed(2)}</span>
                    </div>
                    {index < order.items.length - 1 && <Separator className="mt-3" />}
                  </div>
                ))}
              </div>
              <Separator className="my-4" />
              <div className="flex justify-between items-center font-semibold">
                <span>Total</span>
                <span className="flex items-center gap-1">
                  <DollarSign className="h-4 w-4" />
                  {order.total.toFixed(2)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Special Instructions */}
          {order.specialInstructions && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Special Instructions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{order.specialInstructions}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>

      {/* Actions */}
      {actions.length > 0 && (
        <div className="p-4 border-t border-border">
          <div className="space-y-2">
            {actions.map((action) => (
              <Button
                key={action.status}
                variant={action.variant}
                className="w-full"
                onClick={() => onStatusUpdate(order.id, action.status)}
              >
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
