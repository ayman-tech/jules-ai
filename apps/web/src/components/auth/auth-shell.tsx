"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"
import { BrandMark } from "@/components/app/brand-mark"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

function continuePath() {
  if (typeof window === "undefined") return "/"
  return new URLSearchParams(window.location.search).get("next") || "/"
}

function linkWithNext(path: string) {
  const next = continuePath()
  return next === "/" ? path : `${path}?next=${encodeURIComponent(next)}`
}

export function AuthShell({ children }: { children: React.ReactNode }) {
  return <main className="grid min-h-dvh bg-background lg:grid-cols-[minmax(260px,32%)_1fr]">
    <aside className="hidden flex-col bg-slate-950 px-10 py-12 text-white lg:flex">
      <div className="flex items-center gap-3"><BrandMark /><span className="text-xl font-semibold">Jules AI</span></div>
      <p className="mt-14 max-w-xs text-2xl font-medium leading-snug">Your company&apos;s shared intelligence, ready when you need it.</p>
      <div className="mt-auto text-sm text-slate-400">Private by design · Permission-aware knowledge</div>
    </aside>
    <div className="flex min-h-dvh items-center justify-center px-4 py-10 sm:px-8">{children}</div>
  </main>
}

function FormCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm sm:p-8">
    <div className="mb-7 flex items-center gap-3 lg:hidden"><BrandMark /><span className="font-semibold">Jules AI</span></div>
    <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
    <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
    {children}
  </section>
}

export function SignInScreen() {
  const auth = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true)
    try {
      await auth.signIn(email, password)
      router.replace(continuePath())
    } catch { /* provider exposes the safe error */ } finally { setBusy(false) }
  }
  return <AuthShell><FormCard title="Welcome back" description="Sign in to continue to your Jules workspace.">
    <form className="mt-7" onSubmit={submit}><FieldGroup>
      <Field><FieldLabel htmlFor="email">Work email</FieldLabel><Input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
      <Field><div className="flex items-center justify-between"><FieldLabel htmlFor="password">Password</FieldLabel><Link className="text-sm text-primary hover:underline" href={linkWithNext("/forgot-password")}>Forgot password?</Link></div><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
      {auth.error ? <p className="text-sm text-destructive" role="alert">{auth.error}</p> : null}
      <Button className="w-full" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
    </FieldGroup></form>
    <p className="mt-6 text-center text-sm text-muted-foreground">New to Jules? <Link className="font-medium text-primary hover:underline" href={linkWithNext("/sign-up")}>Create an account</Link></p>
  </FormCard></AuthShell>
}

export function SignUpScreen() {
  const auth = useAuth()
  const router = useRouter()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirmation) { setError("Passwords do not match."); return }
    setBusy(true); setError(null)
    try {
      await auth.signUp(name, email, password, continuePath())
      router.replace(linkWithNext("/verify-email"))
    } catch { /* provider exposes the safe error */ } finally { setBusy(false) }
  }
  return <AuthShell><FormCard title="Create your account" description="Get started with Jules AI.">
    <form className="mt-7" onSubmit={submit}><FieldGroup>
      <Field><FieldLabel htmlFor="display-name">Display name</FieldLabel><Input id="display-name" autoComplete="name" required value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <Field><FieldLabel htmlFor="email">Work email</FieldLabel><Input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field>
      <Field><FieldLabel htmlFor="password">Password</FieldLabel><Input id="password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} /><FieldDescription>Use the password policy configured in Firebase Authentication.</FieldDescription></Field>
      <Field><FieldLabel htmlFor="confirm-password">Confirm password</FieldLabel><Input id="confirm-password" type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></Field>
      {error || auth.error ? <p className="text-sm text-destructive" role="alert">{error || auth.error}</p> : null}
      <Button className="w-full" type="submit" disabled={busy}>{busy ? "Creating account…" : "Create account"}</Button>
    </FieldGroup></form>
    <p className="mt-6 text-center text-sm text-muted-foreground">Already have an account? <Link className="font-medium text-primary hover:underline" href={linkWithNext("/sign-in")}>Sign in</Link></p>
    <p className="mt-6 text-xs leading-relaxed text-muted-foreground">By creating an account, you agree to your organization&apos;s acceptable-use and privacy policies.</p>
  </FormCard></AuthShell>
}

export function ForgotPasswordScreen() {
  const auth = useAuth()
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true)
    try { await auth.resetPassword(email); setSent(true) }
    catch { toast.error("The reset email could not be sent.") }
    finally { setBusy(false) }
  }
  return <AuthShell><FormCard title="Reset your password" description="Enter your email and Firebase will send a secure reset link.">
    {sent ? <div className="mt-7 rounded-lg border bg-muted/40 p-4 text-sm">If an account can receive password resets, an email is on its way.</div> :
      <form className="mt-7" onSubmit={submit}><FieldGroup><Field><FieldLabel htmlFor="email">Work email</FieldLabel><Input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></Field><Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send reset email"}</Button></FieldGroup></form>}
    <p className="mt-6 text-center text-sm"><Link className="text-primary hover:underline" href={linkWithNext("/sign-in")}>Back to sign in</Link></p>
  </FormCard></AuthShell>
}

export function VerifyEmailScreen() {
  const auth = useAuth()
  const router = useRouter()
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  async function check() {
    setBusy(true)
    try {
      if (await auth.refreshVerification()) router.replace(continuePath())
      else toast.error("Email is not verified yet. Open the link in your inbox, then try again.")
    } finally { setBusy(false) }
  }
  return <AuthShell><FormCard title="Verify your email" description={`We sent a verification link to ${auth.firebaseUser?.email ?? "your email address"}.`}>
    <div className="mt-7 space-y-3">
      <Button className="w-full" onClick={() => void check()} disabled={busy}>{busy ? "Checking…" : "I’ve verified my email"}</Button>
      <Button className="w-full" variant="outline" onClick={async () => { await auth.sendVerification(continuePath()); setSent(true) }}>{sent ? "Verification email resent" : "Resend verification email"}</Button>
      <Button className="w-full" variant="ghost" onClick={() => void auth.signOut().then(() => router.replace(linkWithNext("/sign-in")))}>Use another account</Button>
    </div>
  </FormCard></AuthShell>
}
