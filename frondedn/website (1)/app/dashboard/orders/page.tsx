"use client"

import { useState, useEffect } from "react"
import { OrderGrid } from "@/components/dashboard/order-grid"
import { OrderDetails } from "@/components/dashboard/order-details"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Search, Filter, RefreshCw } from "lucide-react"
import { useRef } from "react"
// Replace apiClient with direct fetch calls to backend
import { toast } from "@/hooks/use-toast"

export type OrderStatus = "preparing" | "ready" | "completed" | "cancelled"

export interface Order {
  id: string
  orderNumber: number
  customer: string
  items: Array<{
    name: string
    quantity: number
    price: number
    notes?: string
  }>
  total: number
  status: OrderStatus
  createdAt: string
  estimatedTime?: string
  specialInstructions?: string
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const didRunRef = useRef(false)

  useEffect(() => {
    const loadOrders = async () => {
      try {
        setIsLoading(true)
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
        if (!token) {
          // Not authenticated: do not hit backend; render empty state quietly
          setOrders([])
          return
        }
        const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/orders/active`, {
          headers,
        })
        if (!res.ok) throw new Error(`orders ${res.status}`)
        const data = await res.json()

        // Map backend order shape to UI Order
        const mapped: Order[] = (data || []).map((o: any) => ({
          id: String(o.id),
          orderNumber: Number(o.id) || 0,
          customer: o.table_id ? `Table ${o.table_id}` : "Takeout",
          items: Array.isArray(o.items) ? o.items.map((it: any) => ({
            name: it.name ?? "Item",
            quantity: it.quantity ?? 1,
            price: it.price ?? 0,
            notes: it.notes ?? undefined,
          })) : [],
          total: o.total ?? 0,
          status: (String(o.status).toLowerCase() as OrderStatus) || "preparing",
          createdAt: o.created_at ?? new Date().toISOString(),
          estimatedTime: o.estimated_ready ?? undefined,
          specialInstructions: o.special_instructions ?? undefined,
        }))

        setOrders(mapped)
      } catch (error) {
        // Avoid toast spam; likely unauthorized or server temporarily unavailable
      } finally {
        setIsLoading(false)
      }
    }

    if (didRunRef.current) return
    didRunRef.current = true
    loadOrders()
  }, [])

  const filteredOrders = orders.filter((order) => {
    const matchesStatus = statusFilter === "all" || order.status === statusFilter
    const matchesSearch =
      searchQuery === "" ||
      order.orderNumber.toString().includes(searchQuery) ||
      order.customer.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesSearch
  })

  const statusCounts = {
    preparing: orders.filter((o) => o.status === "preparing").length,
    ready: orders.filter((o) => o.status === "ready").length,
    completed: orders.filter((o) => o.status === "completed").length,
  }

  const updateOrderStatus = async (orderId: string, newStatus: OrderStatus) => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (token) headers["Authorization"] = `Bearer ${token}`

      // Supported transitions in backend kitchen endpoints
      const base = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/kitchen/orders/${encodeURIComponent(orderId)}`
      if (newStatus === "preparing") {
        const res = await fetch(`${base}/start`, { method: "PUT", headers })
        if (!res.ok) throw new Error(`start ${res.status}`)
      } else if (newStatus === "ready") {
        const res = await fetch(`${base}/complete`, { method: "PUT", headers })
        if (!res.ok) throw new Error(`complete ${res.status}`)
      } else {
        // No explicit endpoint; update locally as fallback
      }

      setOrders((prev) => prev.map((order) => (order.id === orderId ? { ...order, status: newStatus } : order)))
      if (selectedOrder?.id === orderId) {
        setSelectedOrder((prev) => (prev ? { ...prev, status: newStatus } : null))
      }
      toast({
        title: "Order updated",
        description: `Order #${orders.find((o) => o.id === orderId)?.orderNumber} status changed to ${newStatus}`,
      })
    } catch (error) {
      toast({
        title: "Update failed",
        description: "Could not update order status. Please try again.",
        variant: "destructive",
      })
    }
  }

  const refreshOrders = async () => {
    try {
      setIsLoading(true)
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      if (!token) {
        setOrders([])
        return
      }
      const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/orders/active`, {
        headers,
      })
      if (!res.ok) throw new Error(`orders ${res.status}`)
      const data = await res.json()
      const mapped: Order[] = (data || []).map((o: any) => ({
        id: String(o.id),
        orderNumber: Number(o.id) || 0,
        customer: o.table_id ? `Table ${o.table_id}` : "Takeout",
        items: Array.isArray(o.items) ? o.items.map((it: any) => ({
          name: it.name ?? "Item",
          quantity: it.quantity ?? 1,
          price: it.price ?? 0,
          notes: it.notes ?? undefined,
        })) : [],
        total: o.total ?? 0,
        status: (String(o.status).toLowerCase() as OrderStatus) || "preparing",
        createdAt: o.created_at ?? new Date().toISOString(),
        estimatedTime: o.estimated_ready ?? undefined,
        specialInstructions: o.special_instructions ?? undefined,
      }))
      setOrders(mapped)
      toast({
        title: "Orders refreshed",
        description: "Order data has been updated from the server.",
      })
    } catch (error) {
      // Quiet fail to avoid noise when auth issues occur
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading orders...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex">
      {/* Main Orders Grid */}
      <div className="flex-1 p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-heading font-bold">Order Management</h1>
              <p className="text-muted-foreground">Track and manage all incoming orders</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
              >
                {statusCounts.preparing} Preparing
              </Badge>
              <Badge variant="outline" className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                {statusCounts.ready} Ready
              </Badge>
              <Button variant="outline" size="sm" onClick={refreshOrders} disabled={isLoading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search orders..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 w-64"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Orders</SelectItem>
                <SelectItem value="preparing">Preparing</SelectItem>
                <SelectItem value="ready">Ready</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Order Grid */}
        {orders.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-center">
            <div>
              <p className="text-muted-foreground mb-2">No orders found</p>
              <p className="text-sm text-muted-foreground">
                Orders will appear here when they are received from your backend
              </p>
            </div>
          </div>
        ) : (
          <OrderGrid orders={filteredOrders} onOrderClick={setSelectedOrder} />
        )}
      </div>

      {/* Order Details Panel */}
      {selectedOrder && (
        <div className="w-96 border-l border-border bg-card">
          <OrderDetails
            order={selectedOrder}
            onClose={() => setSelectedOrder(null)}
            onStatusUpdate={updateOrderStatus}
          />
        </div>
      )}
    </div>
  )
}
