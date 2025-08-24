"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Eye } from "lucide-react"
import { LiveMetrics } from "@/components/realtime/live-metrics"
import { toast } from "@/hooks/use-toast"

interface DashboardStats {
  todaysOrders: number
  totalRevenue: number
  pendingOrders: number
  completedOrders: number
  averageOrderValue: number
  activeConversations: number
  todaysOrdersChange: string
  totalRevenueChange: string
  pendingOrdersChange: string
  completedOrdersChange: string
  averageOrderValueChange: string
  activeConversationsChange: string
}

interface RecentOrder {
  id: string
  orderNumber: string
  customer: string
  amount: number
  status: string
  createdAt: string
}

export function DashboardOverview() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentOrders, setRecentOrders] = useState<RecentOrder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const didRunRef = useRef(false)

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setIsLoading(true)
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
        if (!token) {
          // Not authenticated: do not call backend, just render empty state
          setStats(null)
          setRecentOrders([])
          return
        }
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        }

        const overviewRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/dashboard/overview`, {
          headers,
        })
        if (!overviewRes.ok) throw new Error(`overview ${overviewRes.status}`)
        const overviewJson = await overviewRes.json()

        // Map backend shape to UI shape
        const mappedOverview = {
          todaysOrders: overviewJson.today?.total_orders ?? 0,
          totalRevenue: overviewJson.today?.total_revenue ?? 0,
          pendingOrders: overviewJson.today?.pending_orders ?? 0,
          completedOrders: overviewJson.today?.completed_orders ?? 0,
          averageOrderValue: overviewJson.today?.average_order_value ?? 0,
          activeConversations: overviewJson.active_conversations ?? 0,
          todaysOrdersChange: "",
          totalRevenueChange: "",
          pendingOrdersChange: "",
          completedOrdersChange: "",
          averageOrderValueChange: "",
          activeConversationsChange: "",
        }

        const ordersRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/orders?limit=4`, {
          headers,
        })
        if (!ordersRes.ok) throw new Error(`orders ${ordersRes.status}`)
        const ordersJson = await ordersRes.json()

        const mappedOrders = (ordersJson || []).slice(0, 4).map((o: any) => ({
          id: String(o.id ?? o.order_id ?? Math.random()),
          orderNumber: o.order_number ? `#${o.order_number}` : `#${o.id ?? ""}`,
          customer: o.customer_name ?? "Customer",
          amount: o.total_amount ?? o.total ?? 0,
          status: (typeof o.status === "string" ? o.status : o.status?.value) ?? "pending",
          createdAt: o.created_at ?? new Date().toISOString(),
        }))

        setStats(mappedOverview)
        setRecentOrders(mappedOrders)
      } catch (error) {
        // Avoid toast spam; likely unauthorized or server temporarily unavailable
        setStats(null)
        setRecentOrders([])
      } finally {
        setIsLoading(false)
      }
    }

    if (didRunRef.current) return
    didRunRef.current = true
    fetchDashboardData()
  }, [])

  const getTimeAgo = (dateString: string) => {
    const now = new Date()
    const orderTime = new Date(dateString)
    const diffInMinutes = Math.floor((now.getTime() - orderTime.getTime()) / (1000 * 60))

    if (diffInMinutes < 1) return "Just now"
    if (diffInMinutes < 60) return `${diffInMinutes} min ago`
    const hours = Math.floor(diffInMinutes / 60)
    return `${hours} hour${hours > 1 ? "s" : ""} ago`
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="space-y-2">
                <div className="h-4 bg-muted rounded w-3/4"></div>
                <div className="h-8 bg-muted rounded w-1/2"></div>
              </CardHeader>
            </Card>
          ))}
        </div>
        <Card className="animate-pulse">
          <CardHeader>
            <div className="h-6 bg-muted rounded w-1/4"></div>
          </CardHeader>
          <CardContent className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-muted rounded"></div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <LiveMetrics />

      {/* Recent Orders */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Orders</CardTitle>
              <CardDescription>Latest orders from your customers</CardDescription>
            </div>
            <Button variant="outline" size="sm">
              <Eye className="h-4 w-4 mr-2" />
              View All
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentOrders.map((order) => (
              <div key={order.id} className="flex items-center justify-between p-4 border rounded-lg">
                <div className="flex items-center gap-4">
                  <div>
                    <p className="font-medium">{order.orderNumber}</p>
                    <p className="text-sm text-muted-foreground">{order.customer}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Badge
                    variant={
                      order.status === "completed" ? "default" : order.status === "ready" ? "secondary" : "outline"
                    }
                  >
                    {order.status}
                  </Badge>
                  <div className="text-right">
                    <p className="font-medium">${order.amount.toFixed(2)}</p>
                    <p className="text-sm text-muted-foreground">{getTimeAgo(order.createdAt)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
