"use client"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { Clock, AlertCircle, CheckCircle } from "lucide-react"
import type { Conversation } from "@/app/dashboard/chat/page"

interface ChatListProps {
  conversations: Conversation[]
  selectedConversation: Conversation | null
  onConversationSelect: (conversation: Conversation) => void
}

const statusIcons = {
  waiting: { icon: Clock, color: "text-orange-500" },
  active: { icon: AlertCircle, color: "text-blue-500" },
  resolved: { icon: CheckCircle, color: "text-green-500" },
}

const priorityColors = {
  low: "border-l-gray-400",
  medium: "border-l-yellow-400",
  high: "border-l-red-400",
}

export function ChatList({ conversations, selectedConversation, onConversationSelect }: ChatListProps) {
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60)

    if (diffInHours < 1) {
      const minutes = Math.floor(diffInHours * 60)
      return `${minutes}m ago`
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)}h ago`
    } else {
      return date.toLocaleDateString()
    }
  }

  return (
    <ScrollArea className="flex-1">
      <div className="p-2 space-y-1">
        {conversations.map((conversation) => {
          const StatusIcon = statusIcons[conversation.status].icon
          const isSelected = selectedConversation?.id === conversation.id

          return (
            <div
              key={conversation.id}
              className={cn(
                "p-3 rounded-lg cursor-pointer transition-colors border-l-4",
                priorityColors[conversation.priority],
                isSelected ? "bg-accent text-accent-foreground" : "hover:bg-muted",
              )}
              onClick={() => onConversationSelect(conversation)}
            >
              <div className="flex items-start gap-3">
                <Avatar className="h-10 w-10 flex-shrink-0">
                  <AvatarFallback>
                    {conversation.customer.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm truncate">{conversation.customer.name}</span>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <StatusIcon className={cn("h-3 w-3", statusIcons[conversation.status].color)} />
                      {conversation.unreadCount > 0 && (
                        <Badge className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
                          {conversation.unreadCount}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground truncate mb-2">{conversation.lastMessage.content}</p>

                  <div className="flex items-center justify-between">
                    <div className="flex gap-1">
                      {conversation.tags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-xs px-1 py-0">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <span className="text-xs text-muted-foreground">{formatTime(conversation.updatedAt)}</span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}
