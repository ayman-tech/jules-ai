"use client"

import { Check, Clock3, Copy, MailPlus, Menu, MoreHorizontal, RefreshCw, ShieldCheck, Trash2, UserRound } from "lucide-react"
import { useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AuditEvent, Effort, Invitation, Member, ModelOption } from "@/lib/types"

interface OrganizationViewProps {
  members: Member[]
  invitations: Invitation[]
  auditEvents: AuditEvent[]
  models: ModelOption[]
  organizationName: string
  onInvite: (email: string) => Promise<string | undefined>
  onSavePolicy: (defaultModel: string, maximumEffort: Effort) => void
  onResendInvitation: (id: string) => Promise<string | undefined>
  onRevokeInvitation: (id: string) => void
  onOpenMobileNavigation: () => void
}

export function OrganizationView(props: OrganizationViewProps) {
  const [inviteOpen, setInviteOpen] = useState(false)
  const [email, setEmail] = useState("")
  const [acceptanceLink, setAcceptanceLink] = useState("")
  const [copied, setCopied] = useState(false)
  const [defaultModel, setDefaultModel] = useState(props.models[0]?.id ?? "")
  const [maximumEffort, setMaximumEffort] = useState<Effort>("high")
  return <section className="flex min-w-0 flex-1 flex-col bg-background">
    <header className="flex h-16 shrink-0 items-center gap-3 border-b px-3 sm:px-6 lg:hidden"><Button variant="ghost" size="icon-lg" aria-label="Open navigation" onClick={props.onOpenMobileNavigation}><Menu /></Button><span className="font-semibold">Organization</span></header>
    <div className="overflow-y-auto"><div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-8 sm:py-12"><div className="flex items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{props.organizationName}</h1><p className="mt-1.5 text-sm text-muted-foreground">Manage members, invitations, model access, and organization activity.</p></div><Button onClick={() => setInviteOpen(true)}><MailPlus data-icon="inline-start" />Invite member</Button></div>
      <Tabs defaultValue="members" className="mt-8"><TabsList><TabsTrigger value="members">Members</TabsTrigger><TabsTrigger value="models">Model policy</TabsTrigger><TabsTrigger value="audit">Audit events</TabsTrigger></TabsList>
        <TabsContent value="members" className="mt-6"><div className="overflow-hidden rounded-lg border"><Table><TableHeader><TableRow><TableHead>Member</TableHead><TableHead>Role</TableHead><TableHead>Status</TableHead><TableHead><span className="sr-only">Actions</span></TableHead></TableRow></TableHeader><TableBody>{props.members.map((member) => <TableRow key={member.id}><TableCell><div className="flex items-center gap-3"><Avatar className="size-8"><AvatarFallback>{member.display_name.slice(0, 1)}</AvatarFallback></Avatar><span><span className="block font-medium">{member.display_name}</span><span className="block text-xs text-muted-foreground">{member.email}</span></span></div></TableCell><TableCell><Badge variant="secondary">{member.role}</Badge></TableCell><TableCell><span className="text-sm">Active</span></TableCell><TableCell /></TableRow>)}{props.invitations.filter((item) => item.status === "pending").map((invite) => <TableRow key={invite.id}><TableCell><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-full bg-muted"><Clock3 /></span><span><span className="block font-medium">Invitation pending</span><span className="block text-xs text-muted-foreground">{invite.email}</span></span></div></TableCell><TableCell><Badge variant="outline">member</Badge></TableCell><TableCell><span className="text-sm text-muted-foreground">Expires {new Date(invite.expires_at).toLocaleDateString()}</span></TableCell><TableCell className="text-right"><DropdownMenu><DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${invite.email}`} />}><MoreHorizontal /></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onClick={async () => { const link = await props.onResendInvitation(invite.id); if (link) { setAcceptanceLink(link); setInviteOpen(true) } }}><RefreshCw />Resend</DropdownMenuItem><DropdownMenuItem variant="destructive" onClick={() => props.onRevokeInvitation(invite.id)}><Trash2 />Revoke</DropdownMenuItem></DropdownMenuContent></DropdownMenu></TableCell></TableRow>)}</TableBody></Table></div></TabsContent>
        <TabsContent value="models" className="mt-6"><div className="max-w-xl"><h2 className="font-semibold">Model policy</h2><p className="mt-1 text-sm text-muted-foreground">Control the defaults available to members.</p><FieldGroup className="mt-5"><Field><FieldLabel>Default model</FieldLabel><Select value={defaultModel} onValueChange={(value) => setDefaultModel(value as string)}><SelectTrigger aria-label="Organization default model" className="w-full"><SelectValue>{(value: string) => props.models.find((model) => model.id === value)?.display_name ?? value}</SelectValue></SelectTrigger><SelectContent><SelectGroup>{props.models.map((model) => <SelectItem key={model.id} value={model.id}>{model.display_name}</SelectItem>)}</SelectGroup></SelectContent></Select></Field><Field><FieldLabel>Maximum effort</FieldLabel><Select value={maximumEffort} onValueChange={(value) => setMaximumEffort(value as Effort)}><SelectTrigger aria-label="Organization maximum effort" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem></SelectGroup></SelectContent></Select></Field></FieldGroup><Button className="mt-5" onClick={() => props.onSavePolicy(defaultModel, maximumEffort)}><ShieldCheck data-icon="inline-start" />Save policy</Button></div></TabsContent>
        <TabsContent value="audit" className="mt-6"><div className="flex flex-col divide-y">{props.auditEvents.map((event) => <div key={event.id} className="flex items-start gap-3 py-4"><span className="flex size-8 items-center justify-center rounded-full bg-muted"><UserRound /></span><div className="min-w-0 flex-1"><p className="text-sm font-medium">{event.action.replaceAll(".", " ")}</p><p className="text-xs text-muted-foreground">{event.target_type} · {event.target_id}</p></div><time className="text-xs text-muted-foreground">{new Date(event.created_at).toLocaleDateString()}</time></div>)}</div></TabsContent>
      </Tabs>
    </div></div>
    <Dialog open={inviteOpen} onOpenChange={(open) => { setInviteOpen(open); if (!open) { setAcceptanceLink(""); setCopied(false) } }}><DialogContent><DialogHeader><DialogTitle>{acceptanceLink ? "Copy invitation link" : "Invite a member"}</DialogTitle><DialogDescription>{acceptanceLink ? "This link is shown once. Share it only with the invited person." : "The invitation is valid for seven days. Jules does not email it automatically."}</DialogDescription></DialogHeader>{acceptanceLink ? <FieldGroup><Field><FieldLabel htmlFor="acceptance-link">One-time invitation link</FieldLabel><div className="flex gap-2"><Input id="acceptance-link" readOnly value={acceptanceLink} /><Button type="button" variant="outline" size="icon" aria-label="Copy invitation link" onClick={async () => { await navigator.clipboard.writeText(acceptanceLink); setCopied(true) }}>{copied ? <Check /> : <Copy />}</Button></div></Field></FieldGroup> : <FieldGroup><Field><FieldLabel htmlFor="invite-email">Work email</FieldLabel><Input id="invite-email" type="email" placeholder="name@company.com" value={email} onChange={(event) => setEmail(event.target.value)} /></Field></FieldGroup>}<DialogFooter showCloseButton>{!acceptanceLink ? <Button disabled={!email.includes("@")} onClick={async () => { const link = await props.onInvite(email); setEmail(""); if (link) setAcceptanceLink(link); else setInviteOpen(false) }}>Create invitation</Button> : null}</DialogFooter></DialogContent></Dialog>
  </section>
}
