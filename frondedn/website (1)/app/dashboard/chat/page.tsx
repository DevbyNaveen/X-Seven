"use client"

import { useState, useEffect } from "react"
import { ChatList } from "@/components/chat/chat-list"
import { ChatThread } from "@/components/chat/chat-thread"
import { CustomerContext } from "@/components/chat/customer-context"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Search, Filter, Users, RefreshCw } from "lucide-react"
import { useRef } from "react"
// Replacing apiClient with direct fetch to backend
import { toast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"

export interface Message {
  id: string
  conversationId: string
  sender: "customer" | "agent"
  content: string
  timestamp: string
  read: boolean
  type: "text" | "image" | "file"
  attachments?: Array<{
    name: string
    url: string
    type: string
  }>
}

export interface Conversation {
  id: string
  customer: {
    id: string
    name: string
    email: string
    phone?: string
    avatar?: string
  }
  lastMessage: Message
  unreadCount: number
  status: "waiting" | "active" | "resolved"
  assignedTo?: string
  priority: "low" | "medium" | "high"
  orderHistory: Array<{
    id: string
    orderNumber: number
    total: number
    status: string
    date: string
  }>
  customerValue: number
  tags: string[]
  createdAt: string
  updatedAt: string
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState("all")
  const [isTyping, setIsTyping] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const didRunRef = useRef(false)

  // Reusable fetchers
  const fetchConversations = async () => {
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      if (!token) {
        // Not authenticated: skip hitting protected dashboard endpoint
        setConversations([])
        setIsLoading(false)
        return
      }
      setIsLoading(true)
      const headers: Record<string, string> = { "Content-Type": "application/json", Authorization: `Bearer ${token}` }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/dashboard/conversations?limit=20`, {
        headers,
      })
      if (!res.ok) throw new Error(`conversations ${res.status}`)
      const data = await res.json()

      const mapped: Conversation[] = (data || []).map((c: any) => ({
        id: String(c.session_id),
        customer: {
          id: String(c.session_id),
          name: c.customer_name ?? "Customer",
          email: c.customer_email ?? "",
        },
        lastMessage: {
          id: crypto.randomUUID(),
          conversationId: String(c.session_id),
          sender: "customer",
          content: c.last_message ?? "",
          timestamp: c.last_message_time ?? new Date().toISOString(),
          read: true,
          type: "text",
        },
        unreadCount: 0,
        status: (c.status === "active" ? "active" : c.status === "idle" ? "waiting" : "waiting"),
        assignedTo: undefined,
        priority: "low",
        orderHistory: [],
        customerValue: 0,
        tags: [],
        createdAt: c.last_message_time ?? new Date().toISOString(),
        updatedAt: c.last_message_time ?? new Date().toISOString(),
      }))

      setConversations(mapped)
    } catch (e) {
      // Quietly fail to avoid toast spam on auth/network issues
      setConversations([])
    } finally {
      setIsLoading(false)
    }
  }

  const fetchMessages = async (conversationId: string) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (token) headers["Authorization"] = `Bearer ${token}`

    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat/session/${encodeURIComponent(conversationId)}/messages`,
      { headers },
    )
    if (!res.ok) throw new Error(`messages ${res.status}`)
    const messagesData = await res.json()
    setMessages(messagesData)
  }

  useEffect(() => {
    if (didRunRef.current) return
    didRunRef.current = true
    fetchConversations()
  }, [])

  // Polling refresh every 15s
  useEffect(() => {
    const id = setInterval(() => {
      fetchConversations().catch(() => {})
    }, 15000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const loadMessages = async () => {
      if (!selectedConversation) return
      try {
        await fetchMessages(selectedConversation.id)
      } catch (error) {
        console.error("Failed to load messages:", error)
        toast({ title: "Failed to load messages", description: "Could not load conversation messages.", variant: "destructive" })
      }
    }
    loadMessages()
  }, [selectedConversation])

  const filteredConversations = conversations.filter((conv) => {
    const matchesSearch =
      searchQuery === "" ||
      conv.customer.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.customer.email.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === "all" || conv.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const handleConversationSelect = (conversation: Conversation) => {
    setSelectedConversation(conversation)
    // Mark messages as read
    setConversations((prev) => prev.map((conv) => (conv.id === conversation.id ? { ...conv, unreadCount: 0 } : conv)))
  }

  const handleSendMessage = async (content: string, attachments?: File[]) => {
    if (!selectedConversation) return

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (token) headers["Authorization"] = `Bearer ${token}`

      const body = {
        session_id: selectedConversation.id,
        message: content,
        channel: "dashboard",
        context: {},
      }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat/message`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`send ${res.status}`)
      const data = await res.json()

      const newMessage = {
        id: crypto.randomUUID(),
        conversationId: selectedConversation.id,
        sender: "agent" as const,
        content: content,
        timestamp: new Date().toISOString(),
        read: true,
        type: "text" as const,
      }
      setMessages((prev) => [...prev, newMessage])

      // Re-fetch messages to stay in sync with server
      try {
        await fetchMessages(selectedConversation.id)
      } catch {}

      // Update conversation last message
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === selectedConversation.id
            ? {
                ...conv,
                lastMessage: newMessage,
                updatedAt: new Date().toISOString(),
                status: "active" as const,
              }
            : conv,
        ),
      )

      toast({
        title: "Message sent",
        description: "Your message has been delivered.",
      })
    } catch (error) {
      console.error("Failed to send message:", error)
      toast({
        title: "Failed to send message",
        description: "Could not send message. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleStatusChange = async (conversationId: string, status: Conversation["status"]) => {
    try {
      // No backend endpoint defined; update local state only
      setConversations((prev) => prev.map((conv) => (conv.id === conversationId ? { ...conv, status } : conv)))
      if (selectedConversation?.id === conversationId) {
        setSelectedConversation((prev) => (prev ? { ...prev, status } : null))
      }
      toast({ title: "Status updated", description: `Conversation status changed to ${status}` })
    } catch (error) {
      console.error("Failed to update conversation status:", error)
      toast({ title: "Update failed", description: "Could not update conversation status.", variant: "destructive" })
    }
  }

  const statusCounts = {
    waiting: conversations.filter((c) => c.status === "waiting").length,
    active: conversations.filter((c) => c.status === "active").length,
    resolved: conversations.filter((c) => c.status === "resolved").length,
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading conversations...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex">
      {/* Chat List Sidebar */}
      <div className="w-80 border-r border-border bg-card flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-heading font-semibold">Customer Chat</h1>
            <div className="flex gap-2 items-center">
              <Badge variant="outline" className="text-xs">
                {statusCounts.waiting} Waiting
              </Badge>
              <Badge variant="outline" className="text-xs">
                {statusCounts.active} Active
              </Badge>
              <Button variant="outline" size="sm" onClick={() => fetchConversations()}>
                <RefreshCw className="h-4 w-4 mr-1" /> Refresh
              </Button>
            </div>
          </div>

          {/* Search and Filters */}
          <div className="space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Conversations</SelectItem>
                <SelectItem value="waiting">Waiting</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Conversation List */}
        {conversations.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-center p-4">
            <div>
              <p className="text-muted-foreground mb-2">No conversations found</p>
              <p className="text-sm text-muted-foreground">Customer conversations will appear here</p>
            </div>
          </div>
        ) : (
          <ChatList
            conversations={filteredConversations}
            selectedConversation={selectedConversation}
            onConversationSelect={handleConversationSelect}
          />
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex">
        {selectedConversation ? (
          <>
            {/* Chat Thread */}
            <div className="flex-1 flex flex-col">
              <ChatThread
                conversation={selectedConversation}
                messages={messages}
                onSendMessage={handleSendMessage}
                onStatusChange={handleStatusChange}
                isTyping={isTyping}
              />
            </div>

            {/* Customer Context Panel */}
            <div className="w-80 border-l border-border bg-card">
              <CustomerContext conversation={selectedConversation} />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-center">
            <div className="space-y-4">
              <div className="p-4 bg-muted rounded-full w-fit mx-auto">
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-heading font-semibold">Select a conversation</h3>
                <p className="text-sm text-muted-foreground">Choose a conversation from the list to start chatting</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
