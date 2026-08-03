"use client"

import { ThemeProvider } from "next-themes"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AuthProvider } from "@/components/auth/auth-provider"

export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange><TooltipProvider><AuthProvider>{children}</AuthProvider><Toaster position="top-right" /></TooltipProvider></ThemeProvider>
}
