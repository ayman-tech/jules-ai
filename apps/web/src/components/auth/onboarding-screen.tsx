"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { BrandMark } from "@/components/app/brand-mark"
import { useAuth } from "@/components/auth/auth-provider"
import { OrganizationAccess } from "@/components/organizations/organization-access"
import { Button } from "@/components/ui/button"

export function OnboardingScreen() {
  const auth = useAuth()
  const router = useRouter()
  useEffect(() => {
    if (auth.loading) return
    if (auth.mode === "firebase" && !auth.firebaseUser) router.replace("/sign-in")
    else if (auth.mode === "firebase" && !auth.firebaseUser?.emailVerified) router.replace("/verify-email")
    else if (auth.bootstrap?.organizations.length) router.replace("/")
  }, [auth.bootstrap, auth.firebaseUser, auth.loading, auth.mode, router])

  if (auth.loading) return <CenteredLoading />
  return <main className="min-h-dvh bg-muted/20">
    <header className="border-b bg-background"><div className="mx-auto flex h-16 max-w-6xl items-center px-4 sm:px-8"><div className="flex items-center gap-3"><BrandMark /><span className="font-semibold">Jules AI</span></div><div className="ml-auto flex items-center gap-3 text-sm"><span className="hidden text-muted-foreground sm:inline">{auth.bootstrap?.user.email}</span><Button variant="ghost" size="sm" onClick={() => void auth.signOut().then(() => router.replace("/sign-in"))}>Sign out</Button></div></div></header>
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-8 sm:py-16">
      <div className="mb-8"><h1 className="text-3xl font-semibold tracking-tight">Choose how to get started</h1><p className="mt-2 text-muted-foreground">Create a new workspace or join one with a secure invitation.</p></div>
      <OrganizationAccess onOrganizationReady={(organization) => { localStorage.setItem(`jules:last-organization:${auth.bootstrap?.user.id}`, organization.id); router.replace("/") }} />
    </div>
  </main>
}

function CenteredLoading() {
  return <main className="flex min-h-dvh items-center justify-center bg-background"><p className="text-sm text-muted-foreground">Loading your account…</p></main>
}
