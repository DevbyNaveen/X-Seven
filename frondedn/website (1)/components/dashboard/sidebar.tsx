"use client"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  LayoutDashboard,
  ShoppingCart,
  MessageSquare,
  BarChart3,
  Settings,
  Users,
  ChevronLeft,
  Building2,
} from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"

interface SidebarProps {
  isCollapsed: boolean
  onToggle: () => void
}

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Orders", href: "/dashboard/orders", icon: ShoppingCart },
  { name: "Chat", href: "/dashboard/chat", icon: MessageSquare },
  { name: "Analytics", href: "/dashboard/analytics", icon: BarChart3 },
  { name: "Staff", href: "/dashboard/staff", icon: Users },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
]

export function Sidebar({ isCollapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()
  const [profileName, setProfileName] = useState<string>("")
  const [profileRole, setProfileRole] = useState<string>("")

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
        if (!token) return
        const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/test-token`, { method: "POST", headers })
        if (!res.ok) return
        const data = await res.json()
        setProfileName(data?.name || "")
        setProfileRole((data?.role || "").toString().toLowerCase())
      } catch {
        // ignore
      }
    }
    loadProfile()
  }, [])

  const initials = (profileName || "").trim()
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("") || "--"

  return (
    <div
      className={cn(
        "bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300",
        isCollapsed ? "w-16" : "w-64",
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-between">
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <div className="p-2 bg-sidebar-primary rounded-lg">
                <Building2 className="h-5 w-5 text-sidebar-primary-foreground" />
              </div>
              <div>
                <h2 className="font-heading font-semibold text-sidebar-foreground">Business Hub</h2>
                <p className="text-xs text-sidebar-foreground/70">Dashboard</p>
              </div>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className="text-sidebar-foreground hover:bg-sidebar-accent"
          >
            <ChevronLeft className={cn("h-4 w-4 transition-transform", isCollapsed && "rotate-180")} />
          </Button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            return (
              <li key={item.name}>
                <Link href={item.href}>
                  <Button
                    variant={isActive ? "default" : "ghost"}
                    className={cn(
                      "w-full justify-start gap-3 text-sidebar-foreground",
                      isActive
                        ? "bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90"
                        : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      isCollapsed && "px-2",
                    )}
                  >
                    <item.icon className="h-5 w-5 flex-shrink-0" />
                    {!isCollapsed && <span>{item.name}</span>}
                  </Button>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* User Profile */}
      <div className="p-4 border-t border-sidebar-border">
        <div className={cn("flex items-center gap-3", isCollapsed && "justify-center")}>
          <div className="w-8 h-8 bg-sidebar-primary rounded-full flex items-center justify-center">
            <span className="text-sm font-medium text-sidebar-primary-foreground">{initials}</span>
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">{profileName || ""}</p>
              <p className="text-xs text-sidebar-foreground/70 truncate">{profileRole ? profileRole : ""}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
