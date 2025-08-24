"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MessageSquare, Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { NotificationCenter } from "@/components/realtime/notification-center"

interface DashboardHeaderProps {
  onToggleChat: () => void
  isChatOpen: boolean
}

export function DashboardHeader({ onToggleChat, isChatOpen }: DashboardHeaderProps) {
  return (
    <header className="h-16 border-b border-border bg-card px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h1 className="text-xl font-heading font-semibold">Dashboard</h1>
        <Badge variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Online
        </Badge>
      </div>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search..." className="pl-10 w-64" />
        </div>

        <NotificationCenter />

        {/* Chat Toggle */}
        <Button variant="ghost" size="sm" onClick={onToggleChat} className="relative">
          <MessageSquare className="h-5 w-5" />
          {!isChatOpen && (
            <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
              2
            </Badge>
          )}
        </Button>
      </div>
    </header>
  )
}
