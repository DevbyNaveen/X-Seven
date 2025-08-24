"use client"

import type React from "react"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Card, CardContent } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Bell, Check, X, ShoppingCart, MessageSquare } from "lucide-react"
// Replaced external realtime client with direct WebSocket connection

interface Notification {
  id: string
  type: "order" | "message" | "system"
  title: string
  description: string
  timestamp: string
  read: boolean
  icon: React.ComponentType<{ className?: string }>
}

export function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const didRunRef = useRef(false)

  // Direct WebSocket connection
  useEffect(() => {
    if (didRunRef.current) return
    didRunRef.current = true

    const wsBase = process.env.NEXT_PUBLIC_WS_URL
    if (!wsBase) {
      console.warn("NEXT_PUBLIC_WS_URL is not set; skipping notifications realtime connection")
      return
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const url = `${wsBase.replace(/\/?$/, "")}/ws/dashboard${token ? `?token=${encodeURIComponent(token)}` : ""}`
    const ws = new WebSocket(url)
    let heartbeat: any

    ws.onopen = () => {
      setIsConnected(true)
      heartbeat = setInterval(() => {
        try {
          ws.readyState === WebSocket.OPEN && ws.send("ping")
        } catch {}
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        const type = msg.type

        if (type === "order_created") {
          const data = msg.payload ?? msg
          const notification: Notification = {
            id: Math.random().toString(36).substr(2, 9),
            type: "order",
            title: "New Order",
            description: `Order #${data.orderNumber ?? data.order_id ?? ""} from ${data.customer ?? "Customer"}`,
            timestamp: new Date().toISOString(),
            read: false,
            icon: ShoppingCart,
          }
          setNotifications((prev) => [notification, ...prev])
        } else if (type === "message_received") {
          const data = msg.payload ?? msg
          const notification: Notification = {
            id: Math.random().toString(36).substr(2, 9),
            type: "message",
            title: "New Message",
            description: (data.content ?? "").toString().substring(0, 50) + "...",
            timestamp: new Date().toISOString(),
            read: false,
            icon: MessageSquare,
          }
          setNotifications((prev) => [notification, ...prev])
        } else if (type === "order_updated") {
          const data = msg.payload ?? msg
          if ((data.status ?? data.new_status) === "ready") {
            const notification: Notification = {
              id: Math.random().toString(36).substr(2, 9),
              type: "order",
              title: "Order Ready",
              description: `Order #${data.orderNumber ?? data.order_id ?? ""} is ready for pickup`,
              timestamp: new Date().toISOString(),
              read: false,
              icon: Check,
            }
            setNotifications((prev) => [notification, ...prev])
          }
        }
      } catch (_) {
        // ignore non-JSON
      }
    }

    ws.onerror = () => setIsConnected(false)
    ws.onclose = () => {
      setIsConnected(false)
      if (heartbeat) clearInterval(heartbeat)
    }

    return () => {
      if (heartbeat) clearInterval(heartbeat)
      try { ws.close() } catch {}
    }
  }, [])

  const unreadCount = notifications.filter((n) => !n.read).length

  const markAsRead = (id: string) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }

  const markAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  const removeNotification = (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInMinutes = (now.getTime() - date.getTime()) / (1000 * 60)

    if (diffInMinutes < 1) return "Just now"
    if (diffInMinutes < 60) return `${Math.floor(diffInMinutes)}m ago`
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
          {!isConnected && <div className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full animate-pulse" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-heading font-semibold">Notifications</h3>
            <div className="flex items-center gap-2">
              <div className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`} />
              <span className="text-xs text-muted-foreground">{isConnected ? "Live" : "Offline"}</span>
            </div>
          </div>

          {notifications.length === 0 ? (
            <div className="text-center py-8">
              <Bell className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No notifications yet</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">{unreadCount} unread</span>
                {unreadCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={markAllAsRead}>
                    Mark all read
                  </Button>
                )}
              </div>

              <ScrollArea className="h-80">
                <div className="space-y-2">
                  {notifications.slice(0, 10).map((notification) => {
                    const IconComponent = notification.icon
                    return (
                      <Card
                        key={notification.id}
                        className={`cursor-pointer transition-colors ${!notification.read ? "bg-accent/50" : ""}`}
                        onClick={() => markAsRead(notification.id)}
                      >
                        <CardContent className="p-3">
                          <div className="flex items-start gap-3">
                            <div className="p-2 bg-primary/10 rounded-full">
                              <IconComponent className="h-4 w-4 text-primary" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between">
                                <h4 className="font-medium text-sm">{notification.title}</h4>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 w-6 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    removeNotification(notification.id)
                                  }}
                                >
                                  <X className="h-3 w-3" />
                                </Button>
                              </div>
                              <p className="text-xs text-muted-foreground truncate">{notification.description}</p>
                              <p className="text-xs text-muted-foreground mt-1">{formatTime(notification.timestamp)}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    )
                  })}
                </div>
              </ScrollArea>
            </>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
