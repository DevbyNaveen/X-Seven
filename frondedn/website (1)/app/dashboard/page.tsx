"use client"

import { useState } from "react"
import { Sidebar } from "@/components/dashboard/sidebar"
import { DashboardHeader } from "@/components/dashboard/dashboard-header"
import { ChatPanel } from "@/components/dashboard/chat-panel"
import { DashboardOverview } from "@/components/dashboard/dashboard-overview"

export default function DashboardPage() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isChatOpen, setIsChatOpen] = useState(true)

  return (
    <div className="h-screen bg-background flex">
      {/* Left Sidebar */}
      <Sidebar isCollapsed={isSidebarCollapsed} onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <DashboardHeader onToggleChat={() => setIsChatOpen(!isChatOpen)} isChatOpen={isChatOpen} />

        <div className="flex-1 flex min-h-0">
          {/* Center Panel - Main Dashboard Content */}
          <div className="flex-1 p-6 overflow-auto">
            <DashboardOverview />
          </div>

          {/* Right Panel - Chat Interface */}
          {isChatOpen && (
            <div className="w-80 border-l border-border bg-card">
              <ChatPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
