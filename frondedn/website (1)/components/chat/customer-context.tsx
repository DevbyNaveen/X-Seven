"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Mail, Phone, ShoppingCart, DollarSign, Calendar, Star, Gift, RefreshCw, MessageSquare } from "lucide-react"
import type { Conversation } from "@/app/dashboard/chat/page"

interface CustomerContextProps {
  conversation: Conversation
}

export function CustomerContext({ conversation }: CustomerContextProps) {
  const { customer, orderHistory, customerValue, tags } = conversation

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      case "preparing":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
      case "ready":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h3 className="font-heading font-semibold">Customer Details</h3>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Customer Profile */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <Avatar className="h-12 w-12">
                  <AvatarFallback>
                    {customer.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <CardTitle className="text-base">{customer.name}</CardTitle>
                  <CardDescription>Customer since Jan 2024</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <span>{customer.email}</span>
              </div>
              {customer.phone && (
                <div className="flex items-center gap-2 text-sm">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span>{customer.phone}</span>
                </div>
              )}
              <div className="flex items-center gap-2 text-sm">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <span>Total spent: ${customerValue.toFixed(2)}</span>
              </div>
              <div className="flex gap-1 flex-wrap">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="outline" size="sm" className="w-full justify-start bg-transparent">
                <Gift className="h-4 w-4 mr-2" />
                Apply Discount
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start bg-transparent">
                <RefreshCw className="h-4 w-4 mr-2" />
                Process Refund
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start bg-transparent">
                <Star className="h-4 w-4 mr-2" />
                Add to VIP
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start bg-transparent">
                <MessageSquare className="h-4 w-4 mr-2" />
                Create Ticket
              </Button>
            </CardContent>
          </Card>

          {/* Order History */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ShoppingCart className="h-4 w-4" />
                Order History
              </CardTitle>
              <CardDescription>{orderHistory.length} orders</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {orderHistory.map((order, index) => (
                  <div key={order.id}>
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-medium text-sm">Order #{order.orderNumber}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className={getStatusColor(order.status)}>
                            {order.status}
                          </Badge>
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {formatDate(order.date)}
                          </span>
                        </div>
                      </div>
                      <span className="font-medium text-sm">${order.total.toFixed(2)}</span>
                    </div>
                    {index < orderHistory.length - 1 && <Separator className="mt-3" />}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Customer Stats */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Customer Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Average Order Value</span>
                <span className="font-medium">${(customerValue / orderHistory.length).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Total Orders</span>
                <span className="font-medium">{orderHistory.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Customer Rating</span>
                <div className="flex items-center gap-1">
                  <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                  <span className="font-medium">4.8</span>
                </div>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Last Order</span>
                <span className="font-medium">{formatDate(orderHistory[0]?.date || "")}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </div>
  )
}
