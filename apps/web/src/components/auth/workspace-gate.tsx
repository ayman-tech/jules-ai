"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { JulesApp } from "@/components/app/jules-app"
import { useAuth } from "@/components/auth/auth-provider"
import { demoOrganizations, demoUser } from "@/lib/demo-data"

export function WorkspaceGate() {
  const auth = useAuth()
  const router = useRouter()
  useEffect(() => {
    if (auth.loading || auth.mode === "development") return
    if (!auth.firebaseUser) router.replace("/sign-in")
    else if (!auth.firebaseUser.emailVerified) router.replace("/verify-email")
    else if (auth.bootstrap?.requires_onboarding) router.replace("/onboarding")
  }, [auth.bootstrap, auth.firebaseUser, auth.loading, auth.mode, router])

  if (auth.loading || (auth.mode === "firebase" && (!auth.firebaseUser?.emailVerified || !auth.bootstrap || auth.bootstrap.requires_onboarding))) {
    return <main className="flex min-h-dvh items-center justify-center"><p className="text-sm text-muted-foreground">Loading your workspace…</p></main>
  }
  const userId = auth.bootstrap?.user.id ?? demoUser.id
  const organizations = auth.bootstrap?.organizations ?? demoOrganizations
  const storageKey = `jules:last-organization:${userId}`
  const saved = localStorage.getItem(storageKey)
  const active = organizations.find((item) => item.id === saved) ?? organizations[0]
  return <JulesApp
    key={active.id}
    initialOrganizationId={active.id}
    initialOrganizations={organizations}
    onOrganizationChange={(id) => {
      localStorage.setItem(storageKey, id)
      void auth.refreshBootstrap()
    }}
    onMembershipsChange={() => void auth.refreshBootstrap()}
    onSignOut={auth.mode === "firebase" ? () => void auth.signOut().then(() => router.replace("/sign-in")) : undefined}
  />
}
