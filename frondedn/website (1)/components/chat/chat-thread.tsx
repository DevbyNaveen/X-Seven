"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Textarea } from "@/components/ui/textarea"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Send, Paperclip, Smile, MoreVertical, Phone, Video, Archive, UserPlus } from "lucide-react"
import type { Conversation, Message } from "@/app/dashboard/chat/page"

interface ChatThreadProps {
  conversation: Conversation
  messages: Message[]
  onSendMessage: (content: string, attachments?: File[]) => void
  onStatusChange: (conversationId: string, status: Conversation["status"]) => void
  isTyping?: boolean
}

const quickReplies = [
  "Thank you for contacting us!",
  "Your order is being prepared.",
  "Your order is ready for pickup.",
  "We apologize for the delay.",
  "Is there anything else I can help you with?",
]

export function ChatThread({ conversation, messages, onSendMessage, onStatusChange, isTyping }: ChatThreadProps) {
  const [newMessage, setNewMessage] = useState("")
  const [attachments, setAttachments] = useState<File[]>([])
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSend = () => {
    if (newMessage.trim() || attachments.length > 0) {
      onSendMessage(newMessage, attachments)
      setNewMessage("")
      setAttachments([])
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setAttachments((prev) => [...prev, ...files])
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="h-full flex flex-col">
      {/* Chat Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar className="h-10 w-10">
              <AvatarFallback>
                {conversation.customer.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </AvatarFallback>
            </Avatar>
            <div>
              <h3 className="font-heading font-semibold">{conversation.customer.name}</h3>
              <div className="flex items-center gap-2">
                <Badge
                  variant={
                    conversation.status === "active"
                      ? "default"
                      : conversation.status === "resolved"
                        ? "secondary"
                        : "outline"
                  }
                >
                  {conversation.status}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  {conversation.orderHistory.length} orders • ${conversation.customerValue.toFixed(2)} total
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm">
              <Phone className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm">
              <Video className="h-4 w-4" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onStatusChange(conversation.id, "active")}>
                  <UserPlus className="h-4 w-4 mr-2" />
                  Mark Active
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onStatusChange(conversation.id, "resolved")}>
                  <Archive className="h-4 w-4 mr-2" />
                  Resolve
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollAreaRef}>
        <div className="space-y-4">
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.sender === "agent" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] p-3 rounded-lg ${
                  message.sender === "agent" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                {message.attachments && (
                  <div className="mt-2 space-y-1">
                    {message.attachments.map((attachment, index) => (
                      <div key={index} className="text-xs opacity-80">
                        📎 {attachment.name}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs opacity-70">{formatTime(message.timestamp)}</p>
                  {message.sender === "agent" && (
                    <span className="text-xs opacity-70">{message.read ? "Read" : "Sent"}</span>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-muted text-muted-foreground p-3 rounded-lg">
                <div className="flex items-center gap-1">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-current rounded-full animate-bounce" />
                    <div
                      className="w-2 h-2 bg-current rounded-full animate-bounce"
                      style={{ animationDelay: "0.1s" }}
                    />
                    <div
                      className="w-2 h-2 bg-current rounded-full animate-bounce"
                      style={{ animationDelay: "0.2s" }}
                    />
                  </div>
                  <span className="text-xs ml-2">Customer is typing...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Quick Replies */}
      <div className="px-4 py-2 border-t border-border">
        <div className="flex gap-2 overflow-x-auto">
          {quickReplies.map((reply) => (
            <Button
              key={reply}
              variant="outline"
              size="sm"
              className="whitespace-nowrap bg-transparent"
              onClick={() => setNewMessage(reply)}
            >
              {reply}
            </Button>
          ))}
        </div>
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-border">
        {attachments.length > 0 && (
          <div className="mb-2 flex gap-2">
            {attachments.map((file, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                📎 {file.name}
                <button
                  onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== index))}
                  className="ml-1 text-xs"
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Textarea
              placeholder="Type your message..."
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              className="min-h-[40px] max-h-32 resize-none pr-20"
            />
            <div className="absolute right-2 top-2 flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} className="h-6 w-6 p-0">
                <Paperclip className="h-3 w-3" />
              </Button>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                <Smile className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <Button onClick={handleSend} disabled={!newMessage.trim() && attachments.length === 0}>
            <Send className="h-4 w-4" />
          </Button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          accept="image/*,.pdf,.doc,.docx,.txt"
        />
      </div>
    </div>
  )
}
