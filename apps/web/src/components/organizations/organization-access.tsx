"use client"

import { Building2, Link2, Plus, ShieldCheck } from "lucide-react"
import { useState, type FormEvent } from "react"
import { useAuth } from "@/components/auth/auth-provider"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { julesApi } from "@/lib/api"
import type { InvitationPreview, Organization } from "@/lib/types"

export function invitationToken(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ""
  try {
    const url = new URL(trimmed)
    const segments = url.pathname.split("/").filter(Boolean)
    const inviteIndex = segments.lastIndexOf("invite")
    return inviteIndex >= 0 ? segments[inviteIndex + 1] ?? "" : trimmed
  } catch {
    const marker = "/invite/"
    return trimmed.includes(marker) ? trimmed.split(marker).pop()?.split(/[?#]/)[0] ?? "" : trimmed
  }
}

interface OrganizationAccessProps {
  onOrganizationReady: (organization: Organization) => void
  compact?: boolean
}

export function OrganizationAccess({ onOrganizationReady, compact = false }: OrganizationAccessProps) {
  const auth = useAuth()
  const [name, setName] = useState("")
  const [code, setCode] = useState("")
  const [preview, setPreview] = useState<InvitationPreview | null>(null)
  const [creating, setCreating] = useState(false)
  const [joining, setJoining] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create(event: FormEvent) {
    event.preventDefault(); setCreating(true); setError(null)
    try {
      const organization = await julesApi.createOrganization(name)
      await auth.refreshBootstrap()
      onOrganizationReady(organization)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Organization could not be created.")
    } finally { setCreating(false) }
  }

  async function loadPreview(event?: FormEvent) {
    event?.preventDefault(); setJoining(true); setError(null)
    try {
      const token = invitationToken(code)
      if (!token) throw new Error("Enter an invitation link or code.")
      setPreview(await julesApi.invitationPreview(token))
    } catch (cause) {
      setPreview(null)
      setError(cause instanceof Error ? cause.message : "Invitation could not be previewed.")
    } finally { setJoining(false) }
  }

  async function accept() {
    setJoining(true); setError(null)
    try {
      const result = await julesApi.acceptInvitation(invitationToken(code))
      await auth.refreshBootstrap()
      onOrganizationReady(result.organization)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation could not be accepted.")
    } finally { setJoining(false) }
  }

  return <div className={compact ? "grid gap-5" : "grid gap-5 lg:grid-cols-2"}>
    <form onSubmit={create} className="flex flex-col rounded-xl border bg-card p-5 sm:p-6">
      <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><Plus /></span>
      <h2 className="mt-4 text-lg font-semibold">Create an organization</h2>
      <p className="mt-1 text-sm text-muted-foreground">You become the owner and can invite colleagues or create company knowledge.</p>
      <FieldGroup className="mt-6"><Field><FieldLabel htmlFor={`organization-name-${compact}`}>Organization name</FieldLabel><Input id={`organization-name-${compact}`} placeholder="Northstar" minLength={2} maxLength={180} required value={name} onChange={(event) => setName(event.target.value)} /><FieldDescription>You can change the display name later.</FieldDescription></Field></FieldGroup>
      <Button className="mt-6 w-full" type="submit" disabled={creating}>{creating ? "Creating…" : "Create organization"}</Button>
    </form>

    <form onSubmit={loadPreview} className="flex flex-col rounded-xl border bg-card p-5 sm:p-6">
      <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary"><Link2 /></span>
      <h2 className="mt-4 text-lg font-semibold">Join an organization</h2>
      <p className="mt-1 text-sm text-muted-foreground">Use the private invitation link or code shared by an owner or admin.</p>
      <FieldGroup className="mt-6"><Field><FieldLabel htmlFor={`invitation-code-${compact}`}>Invitation link or code</FieldLabel><Input id={`invitation-code-${compact}`} placeholder="https://jules.ai/invite/…" required value={code} onChange={(event) => { setCode(event.target.value); setPreview(null) }} /><FieldDescription className="flex items-start gap-1.5"><ShieldCheck className="mt-0.5 size-3.5 shrink-0" />Only the invited email address can accept it.</FieldDescription></Field></FieldGroup>
      {preview ? <div className="mt-4 rounded-lg border bg-muted/30 p-4 text-sm">
        <div className="flex items-center gap-2 font-medium"><Building2 className="size-4" />{preview.organization.name}</div>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-muted-foreground"><dt>Invited email</dt><dd>{preview.invited_email}</dd><dt>Role</dt><dd className="capitalize">{preview.role}</dd><dt>Status</dt><dd className="capitalize">{preview.status}</dd></dl>
      </div> : null}
      {preview ? <Button className="mt-4 w-full" type="button" onClick={() => void accept()} disabled={joining || !["pending", "accepted"].includes(preview.status)}>{joining ? "Joining…" : `Join ${preview.organization.name}`}</Button> :
        <Button className="mt-6 w-full" type="submit" variant="outline" disabled={joining}>{joining ? "Checking…" : "Preview invitation"}</Button>}
    </form>
    {error ? <p className="text-sm text-destructive lg:col-span-2" role="alert">{error}</p> : null}
  </div>
}
