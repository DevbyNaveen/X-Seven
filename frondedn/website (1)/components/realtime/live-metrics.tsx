"use client"

import type React from "react"

import { useState, useEffect, useCallback, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TrendingUp, TrendingDown, Activity } from "lucide-react"
// Replaced external realtime client with direct WebSocket connection

interface LiveMetric {
  label: string
  value: number
  change: number
  trend: "up" | "down"
  icon: React.ComponentType<{ className?: string }>
}

export function LiveMetrics() {
  const [metrics, setMetrics] = useState<LiveMetric[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const didRunRef = useRef(false)

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
        if (!token) {
          setMetrics([])
          return
        }
        const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/dashboard/overview`, { headers })
        if (!res.ok) throw new Error(`overview ${res.status}`)
        const json = await res.json()

        const data = {
          pendingOrders: json.today?.pending_orders ?? 0,
          totalRevenue: json.today?.total_revenue ?? 0,
        }

        setMetrics([
          {
            label: "Active Orders",
            value: data.pendingOrders,
            change: 0,
            trend: "up",
            icon: Activity,
          },
          {
            label: "Today's Revenue",
            value: data.totalRevenue,
            change: 0,
            trend: "up",
            icon: TrendingUp,
          },
        ])
      } catch (error) {
        setMetrics([])
      } finally {
        setIsLoading(false)
      }
    }

    if (didRunRef.current) return
    didRunRef.current = true
    fetchMetrics()
  }, [])

  const handleMetricsUpdate = useCallback((data: any) => {
    setMetrics((prev) =>
      prev.map((metric) => {
        const key = metric.label.toLowerCase().replace(/\s+/g, "_")
        if (typeof data[key] === "number") {
          const newValue = data[key]
          const change = newValue - metric.value
          return {
            ...metric,
            value: newValue,
            change,
            trend: change >= 0 ? "up" : "down",
          }
        }
        return metric
      }),
    )
  }, [])

  const handleOrderCreated = useCallback(() => {
    setMetrics((prev) =>
      prev.map((metric) => {
        if (metric.label === "Active Orders") {
          const newValue = metric.value + 1
          const change = newValue - metric.value
          return { ...metric, value: newValue, change, trend: change >= 0 ? "up" : "down" }
        }
        return metric
      }),
    )
  }, [])

  const handleOrderUpdated = useCallback((data: any) => {
    if (data.status === "completed") {
      setMetrics((prev) =>
        prev.map((metric) => {
          if (metric.label === "Active Orders") {
            const newValue = Math.max(0, metric.value - 1)
            const change = newValue - metric.value
            return { ...metric, value: newValue, change, trend: change >= 0 ? "up" : "down" }
          }
          return metric
        }),
      )
    }
  }, [])

  // Direct WebSocket connection to backend
  useEffect(() => {
    const wsBase = process.env.NEXT_PUBLIC_WS_URL
    if (!wsBase) {
      console.warn("NEXT_PUBLIC_WS_URL is not set; skipping realtime connection")
      return
    }
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    if (!token) {
      console.log("[v0] Not authenticated, skipping WebSocket connection")
      return
    }
    const url = `${wsBase.replace(/\/?$/, "")}/ws/dashboard?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    let heartbeat: any

    ws.onopen = () => {
      // Heartbeat to satisfy server receive loop and keep the connection alive
      heartbeat = setInterval(() => {
        try {
          ws.readyState === WebSocket.OPEN && ws.send("ping")
        } catch {}
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case "metrics_updated":
            handleMetricsUpdate(msg.payload ?? msg)
            break
          case "order_created":
            handleOrderCreated()
            break
          case "order_updated":
            handleOrderUpdated(msg.payload ?? msg)
            break
          default:
            // ignore unknown
            break
        }
      } catch (e) {
        // Non-JSON messages (e.g., pings) can be ignored
      }
    }

    ws.onerror = () => {}

    ws.onclose = () => {
      if (heartbeat) clearInterval(heartbeat)
    }

    return () => {
      if (heartbeat) clearInterval(heartbeat)
      try { ws.close() } catch {}
    }
  }, [handleMetricsUpdate, handleOrderCreated, handleOrderUpdated])

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="space-y-2">
              <div className="h-4 bg-muted rounded w-3/4"></div>
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-muted rounded w-1/2 mb-2"></div>
              <div className="h-4 bg-muted rounded w-2/3"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {metrics.map((metric) => {
        const IconComponent = metric.icon
        return (
          <Card key={metric.label} className="relative overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{metric.label}</CardTitle>
              <IconComponent className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-heading font-bold">
                {metric.label.includes("Revenue") ? `$${metric.value.toLocaleString()}` : metric.value}
                {metric.label.includes("Time") && "m"}
              </div>
              <div className="flex items-center text-xs text-muted-foreground">
                {metric.trend === "up" ? (
                  <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-500 mr-1" />
                )}
                <span className={metric.trend === "up" ? "text-green-600" : "text-red-600"}>
                  {metric.change > 0 ? "+" : ""}
                  {metric.change}
                </span>
                <span className="ml-1">from last hour</span>
              </div>
            </CardContent>
            <div className="absolute top-0 right-0 w-1 h-full bg-primary animate-pulse" />
          </Card>
        )
      })}
    </div>
  )
}
