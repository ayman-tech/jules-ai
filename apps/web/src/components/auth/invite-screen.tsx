"use client"

import { Building2, Clock3, Mail, ShieldCheck } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { BrandMark } from "@/components/app/brand-mark"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { julesApi } from "@/lib/api"
import type { InvitationPreview } from "@/lib/types"

export function InviteScreen({ token }: { token: string }) {
  const auth = useAuth()
  const router = useRouter()
  const [preview, setPreview] = useState<InvitationPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const next = `/invite/${encodeURIComponent(token)}`

  useEffect(() => {
    julesApi.invitationPreview(token).then(setPreview).catch((cause) => setError(cause instanceof Error ? cause.message : "Invitation not found"))
  }, [token])

  async function accept() {
    setBusy(true); setError(null)
    try {
      const result = await julesApi.acceptInvitation(token)
      const nextBootstrap = await auth.refreshBootstrap()
      if (nextBootstrap?.user) localStorage.setItem(`jules:last-organization:${nextBootstrap.user.id}`, result.organization.id)
      router.replace("/")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation could not be accepted.")
    } finally { setBusy(false) }
  }

  return <main className="min-h-dvh bg-muted/30 px-4 py-8 sm:py-14">
    <div className="mx-auto mb-7 flex max-w-md items-center gap-3"><BrandMark /><span className="font-semibold">Jules AI</span></div>
    <section className="mx-auto max-w-md overflow-hidden rounded-xl border bg-card shadow-sm">
      {preview ? <>
        <div className="px-6 py-8 text-center"><span className="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary"><Building2 /></span><p className="mt-5 text-sm text-muted-foreground">You&apos;re invited to join</p><h1 className="mt-1 text-2xl font-semibold">{preview.organization.name}</h1></div>
        <dl className="space-y-4 border-y px-6 py-5 text-sm">
          <div className="flex gap-3"><Mail className="mt-0.5 size-4 text-muted-foreground" /><div><dt className="text-muted-foreground">Invited email</dt><dd className="mt-0.5 font-medium">{preview.invited_email}</dd></div></div>
          <div className="flex gap-3"><ShieldCheck className="mt-0.5 size-4 text-muted-foreground" /><div><dt className="text-muted-foreground">Role</dt><dd className="mt-0.5 font-medium capitalize">{preview.role}</dd></div></div>
          <div className="flex gap-3"><Clock3 className="mt-0.5 size-4 text-muted-foreground" /><div><dt className="text-muted-foreground">Expires</dt><dd className="mt-0.5 font-medium">{new Date(preview.expires_at).toLocaleString()}</dd></div></div>
        </dl>
        <div className="space-y-3 p-6">
          {!auth.loading && !auth.firebaseUser && auth.mode === "firebase" ? <>
            <Button className="w-full" render={<Link href={`/sign-in?next=${encodeURIComponent(next)}`} />}>Sign in to join</Button>
            <Button className="w-full" variant="outline" render={<Link href={`/sign-up?next=${encodeURIComponent(next)}`} />}>Create an account</Button>
          </> : auth.mode === "firebase" && !auth.firebaseUser?.emailVerified ? <Button className="w-full" render={<Link href={`/verify-email?next=${encodeURIComponent(next)}`} />}>Verify email to join</Button> :
            <Button className="w-full" onClick={() => void accept()} disabled={busy || !["pending", "accepted"].includes(preview.status)}>{busy ? "Joining…" : `Join ${preview.organization.name}`}</Button>}
          {auth.firebaseUser ? <Button className="w-full" variant="ghost" onClick={() => void auth.signOut().then(() => router.replace(`/sign-in?next=${encodeURIComponent(next)}`))}>Use another account</Button> : null}
        </div>
      </> : <div className="p-8 text-center"><h1 className="text-xl font-semibold">{error ? "Invitation unavailable" : "Checking invitation…"}</h1>{error ? <p className="mt-2 text-sm text-muted-foreground">{error}</p> : null}</div>}
    </section>
  </main>
}
