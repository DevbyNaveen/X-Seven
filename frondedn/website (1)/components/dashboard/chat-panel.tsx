"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Send, MoreVertical, Phone, Video } from "lucide-react"

const conversations = [
  {
    id: 1,
    customer: "Sarah Johnson",
    lastMessage: "Hi, I have a question about my order #1234",
    time: "2 min ago",
    unread: 2,
    status: "waiting",
  },
  {
    id: 2,
    customer: "Mike Chen",
    lastMessage: "Thank you for the quick response!",
    time: "15 min ago",
    unread: 0,
    status: "resolved",
  },
  {
    id: 3,
    customer: "Emma Wilson",
    lastMessage: "When will my order be ready?",
    time: "1 hour ago",
    unread: 1,
    status: "waiting",
  },
]

const messages = [
  {
    id: 1,
    sender: "customer",
    message: "Hi, I have a question about my order #1234",
    time: "2:30 PM",
  },
  {
    id: 2,
    sender: "agent",
    message: "Hello! I'd be happy to help you with your order. Let me check the status for you.",
    time: "2:31 PM",
  },
  {
    id: 3,
    sender: "customer",
    message: "Thank you! I'm wondering when it will be ready for pickup.",
    time: "2:32 PM",
  },
]

export function ChatPanel() {
  const [selectedConversation, setSelectedConversation] = useState(conversations[0])
  const [newMessage, setNewMessage] = useState("")

  const handleSendMessage = () => {
    if (newMessage.trim()) {
      // Handle sending message
      setNewMessage("")
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Chat Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <h3 className="font-heading font-semibold">Customer Chat</h3>
          <Badge variant="secondary">3 Active</Badge>
        </div>
      </div>

      {/* Conversation List */}
      <div className="border-b border-border">
        <ScrollArea className="h-48">
          <div className="p-2">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  selectedConversation.id === conversation.id ? "bg-accent text-accent-foreground" : "hover:bg-muted"
                }`}
                onClick={() => setSelectedConversation(conversation)}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{conversation.customer}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{conversation.time}</span>
                    {conversation.unread > 0 && (
                      <Badge className="h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
                        {conversation.unread}
                      </Badge>
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground truncate">{conversation.lastMessage}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Active Conversation */}
      <div className="flex-1 flex flex-col">
        {/* Conversation Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarFallback>
                  {selectedConversation.customer
                    .split(" ")
                    .map((n) => n[0])
                    .join("")}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium text-sm">{selectedConversation.customer}</p>
                <p className="text-xs text-muted-foreground">Order #1234</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm">
                <Phone className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm">
                <Video className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-4">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.sender === "agent" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] p-3 rounded-lg ${
                    message.sender === "agent" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}
                >
                  <p className="text-sm">{message.message}</p>
                  <p className="text-xs opacity-70 mt-1">{message.time}</p>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        {/* Message Input */}
        <div className="p-4 border-t border-border">
          <div className="flex gap-2">
            <Input
              placeholder="Type a message..."
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
            />
            <Button onClick={handleSendMessage} size="sm">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
