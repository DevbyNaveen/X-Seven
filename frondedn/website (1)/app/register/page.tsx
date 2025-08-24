"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Eye, EyeOff, Building2 } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
// Removed apiClient usage for registration to align with backend schema directly
import { toast } from "@/hooks/use-toast"

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [formData, setFormData] = useState({
    businessName: "",
    businessSlug: "",
    adminName: "",
    email: "",
    password: "",
    phone: "",
    businessCategory: "",
  })
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  

  const slugify = (value: string) =>
    value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const payload = {
        business_name: formData.businessName,
        business_slug: formData.businessSlug || slugify(formData.businessName),
        admin_name: formData.adminName,
        admin_email: formData.email,
        admin_password: formData.password,
        admin_phone: formData.phone || undefined,
        business_category: formData.businessCategory || undefined,
      }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        // Try to parse server error
        let serverDetail = ""
        try {
          const errJson = await res.json()
          serverDetail = typeof errJson?.detail === "string" ? errJson.detail : JSON.stringify(errJson)
        } catch {
          serverDetail = await res.text().catch(() => "")
        }
        const message = `Registration failed (${res.status})${serverDetail ? `: ${serverDetail}` : ""}`
        throw new Error(message)
      }

      const data = await res.json()

      // Optionally persist token for subsequent requests
      if (data?.access_token) {
        try {
          localStorage.setItem("access_token", data.access_token)
        } catch {}
      }

      toast({
        title: "Registration successful",
        description: `Welcome – your business has been created.`,
      })

      router.push("/dashboard")
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Unknown error occurred"

      let title = "Registration failed"
      let description = "Please check your information and try again."
      let variant: "default" | "destructive" = "destructive"

      if (errorMessage.includes("409") || errorMessage.toLowerCase().includes("already exists")) {
        title = "Duplicate detected"
        description = "Business slug or email already exists. Use a different slug/email."
        variant = "destructive"
      } else if (errorMessage.includes("Cannot connect to backend")) {
        title = "Backend connection failed"
        description = "Your backend is not accessible. Please check if it's running and try again."
        variant = "destructive"
      } else if (errorMessage.includes("Endpoint not found")) {
        title = "Backend endpoint missing"
        description = "Your backend doesn't implement the required registration endpoint."
        variant = "destructive"
      } else if (errorMessage.includes("CORS")) {
        title = "CORS configuration needed"
        description = "Your backend needs to allow cross-origin requests from this domain."
        variant = "destructive"
      }

      toast({
        title,
        description,
        variant,
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 bg-primary rounded-lg">
              <Building2 className="h-8 w-8 text-primary-foreground" />
            </div>
          </div>
          <CardTitle className="text-2xl font-heading">Create Account</CardTitle>
          <CardDescription>Set up your business dashboard</CardDescription>
        </CardHeader>
        <CardContent>
          

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="businessName">Business Name</Label>
              <Input
                id="businessName"
                placeholder="Enter your business name"
                value={formData.businessName}
                onChange={(e) => setFormData({ ...formData, businessName: e.target.value })}
                autoComplete="organization"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Admin Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="Enter admin email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                autoComplete="email"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="adminName">Admin Name</Label>
              <Input
                id="adminName"
                placeholder="Enter admin name"
                value={formData.adminName}
                onChange={(e) => setFormData({ ...formData, adminName: e.target.value })}
                autoComplete="name"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="businessSlug">Business Slug</Label>
              <Input
                id="businessSlug"
                placeholder="e.g. sunrise-cafe"
                value={formData.businessSlug}
                onChange={(e) => setFormData({ ...formData, businessSlug: slugify(e.target.value) })}
                onBlur={() =>
                  setFormData((s) => ({ ...s, businessSlug: s.businessSlug || slugify(s.businessName) }))
                }
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="businessCategory">Business Category</Label>
              <select
                id="businessCategory"
                className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={formData.businessCategory}
                onChange={(e) => setFormData({ ...formData, businessCategory: e.target.value })}
                required
              >
                <option value="" disabled>
                  Select a category
                </option>
                <option value="food_hospitality">Food & Hospitality</option>
                <option value="beauty_personal_care">Beauty & Personal Care</option>
                <option value="automotive_services">Automotive Services</option>
                <option value="health_medical">Health & Medical</option>
                <option value="local_services">Local Services</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Admin Phone (optional)</Label>
              <Input
                id="phone"
                placeholder="+1234567890"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                autoComplete="tel"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Create a password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  autoComplete="new-password"
                  required
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Creating account..." : "Create Account"}
            </Button>
          </form>
          

          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link href="/login" className="text-primary hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
