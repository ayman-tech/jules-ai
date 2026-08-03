"use client"

import { Building2, Check, Download, Menu, Palette, Plus, Save, Trash2, Upload } from "lucide-react"
import { useTheme } from "next-themes"
import { useRef, useState } from "react"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { Effort, ModelOption, Organization, OrganizationBrandKit, UserSettings } from "@/lib/types"

interface SettingsViewProps {
  settings: UserSettings
  brandKit: OrganizationBrandKit
  models: ModelOption[]
  organizations: Organization[]
  activeOrganizationId: string
  onOrganizationChange: (id: string) => void
  onManageOrganizations: () => void
  onLeaveOrganization: (id: string) => void
  onSave: (settings: UserSettings) => void
  onSaveBrandKit: (brandKit: OrganizationBrandKit) => void
  onUploadBrandLogo: (file: File) => void
  onDeleteAllConversations: () => void
  onDeleteAccount: () => void
  onOpenMobileNavigation: () => void
}

export function SettingsView(props: SettingsViewProps) {
  const [draft, setDraft] = useState(props.settings)
  const [brandDraft, setBrandDraft] = useState(props.brandKit)
  const logoInput = useRef<HTMLInputElement>(null)
  const { setTheme } = useTheme()
  return <section className="flex min-w-0 flex-1 flex-col bg-background">
    <header className="flex h-16 shrink-0 items-center gap-3 border-b px-3 sm:px-6 lg:hidden"><Button variant="ghost" size="icon-lg" aria-label="Open navigation" onClick={props.onOpenMobileNavigation}><Menu /></Button><span className="font-semibold">Settings</span></header>
    <div className="overflow-y-auto"><div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-8 sm:py-12">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Settings</h1><p className="mt-1.5 text-sm text-muted-foreground">Personal preferences apply only to your account.</p>
      <section className="mt-10"><h2 className="text-base font-semibold">Assistant preferences</h2><p className="mt-1 text-sm text-muted-foreground">Guide how Jules AI responds in your private conversations.</p>
        <FieldGroup className="mt-5"><Field><FieldLabel htmlFor="instructions">Custom instructions</FieldLabel><Textarea id="instructions" className="min-h-32" value={draft.custom_instructions} onChange={(event) => setDraft((current) => ({ ...current, custom_instructions: event.target.value }))} /><FieldDescription>Application security rules always take priority.</FieldDescription></Field>
          <div className="grid gap-4 sm:grid-cols-2"><Field><FieldLabel>Default model</FieldLabel><Select value={draft.default_model} onValueChange={(value) => setDraft((current) => ({ ...current, default_model: value as string }))}><SelectTrigger aria-label="Default model" className="w-full"><SelectValue>{(value: string) => props.models.find((model) => model.id === value)?.display_name ?? value}</SelectValue></SelectTrigger><SelectContent><SelectGroup>{props.models.map((model) => <SelectItem key={model.id} value={model.id}>{model.display_name}</SelectItem>)}</SelectGroup></SelectContent></Select></Field><Field><FieldLabel>Default effort</FieldLabel><Select value={draft.default_effort} onValueChange={(value) => setDraft((current) => ({ ...current, default_effort: value as Effort }))}><SelectTrigger aria-label="Default effort" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem></SelectGroup></SelectContent></Select></Field></div>
          <Field orientation="horizontal" className="items-center justify-between rounded-xl border p-4"><div><FieldLabel htmlFor="web-search-default">Use web search by default</FieldLabel><FieldDescription>New conversations can research public, current information. You can override this in the composer.</FieldDescription></div><Switch id="web-search-default" checked={draft.web_search_default} onCheckedChange={(checked) => setDraft((current) => ({ ...current, web_search_default: checked }))} /></Field>
        </FieldGroup>
      </section>
      <Separator className="my-9" />
      <section><h2 className="text-base font-semibold">Appearance</h2><p className="mt-1 text-sm text-muted-foreground">Use your device preference or choose a theme.</p><Field className="mt-5 max-w-xs"><FieldLabel>Theme</FieldLabel><Select value={draft.theme} onValueChange={(value) => { const theme = value as UserSettings["theme"]; setDraft((current) => ({ ...current, theme })); setTheme(theme) }}><SelectTrigger aria-label="Theme" className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="system">System</SelectItem><SelectItem value="light">Light</SelectItem><SelectItem value="dark">Dark</SelectItem></SelectGroup></SelectContent></Select></Field></section>
      <div className="mt-7"><Button onClick={() => props.onSave(draft)}><Save data-icon="inline-start" />Save preferences</Button></div>
      <Separator className="my-9" />
      <section><div className="flex items-start gap-3"><span className="mt-0.5 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><Palette /></span><div><h2 className="text-base font-semibold">Organization brand kit</h2><p className="mt-1 text-sm text-muted-foreground">Applied to editable documents and presentations generated in this organization.</p></div></div>
        <div className="mt-5 grid gap-5 rounded-xl border p-5">
          <div className="flex flex-wrap items-center gap-3"><input ref={logoInput} type="file" accept="image/png,image/jpeg" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) props.onUploadBrandLogo(file); event.target.value = "" }} /><Button variant="outline" disabled={!brandDraft.can_manage} onClick={() => logoInput.current?.click()}><Upload data-icon="inline-start" />{brandDraft.has_logo ? "Replace logo" : "Upload logo"}</Button><span className="text-xs text-muted-foreground">{brandDraft.logo_file_name ?? "PNG or JPEG, up to 5 MB"}</span></div>
          <div className="grid gap-4 sm:grid-cols-2"><Field><FieldLabel htmlFor="primary-color">Primary color</FieldLabel><div className="flex gap-2"><Input id="primary-color" type="color" className="w-14 px-1" value={brandDraft.primary_color} disabled={!brandDraft.can_manage} onChange={(event) => setBrandDraft((current) => ({ ...current, primary_color: event.target.value }))} /><Input value={brandDraft.primary_color} disabled={!brandDraft.can_manage} onChange={(event) => setBrandDraft((current) => ({ ...current, primary_color: event.target.value }))} /></div></Field><Field><FieldLabel htmlFor="accent-color">Accent color</FieldLabel><div className="flex gap-2"><Input id="accent-color" type="color" className="w-14 px-1" value={brandDraft.accent_color} disabled={!brandDraft.can_manage} onChange={(event) => setBrandDraft((current) => ({ ...current, accent_color: event.target.value }))} /><Input value={brandDraft.accent_color} disabled={!brandDraft.can_manage} onChange={(event) => setBrandDraft((current) => ({ ...current, accent_color: event.target.value }))} /></div></Field></div>
          <div className="grid gap-4 sm:grid-cols-2"><Field><FieldLabel>Heading font</FieldLabel><Select value={brandDraft.heading_font} disabled={!brandDraft.can_manage} onValueChange={(value) => setBrandDraft((current) => ({ ...current, heading_font: value as string }))}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{brandDraft.available_fonts.map((font) => <SelectItem key={font} value={font}>{font}</SelectItem>)}</SelectGroup></SelectContent></Select></Field><Field><FieldLabel>Body font</FieldLabel><Select value={brandDraft.body_font} disabled={!brandDraft.can_manage} onValueChange={(value) => setBrandDraft((current) => ({ ...current, body_font: value as string }))}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{brandDraft.available_fonts.map((font) => <SelectItem key={font} value={font}>{font}</SelectItem>)}</SelectGroup></SelectContent></Select></Field></div>
          <Field><FieldLabel htmlFor="brand-footer">Footer text</FieldLabel><Input id="brand-footer" value={brandDraft.footer_text} disabled={!brandDraft.can_manage} placeholder="Company name or confidentiality notice" onChange={(event) => setBrandDraft((current) => ({ ...current, footer_text: event.target.value }))} /></Field>
          <div className="rounded-lg p-5" style={{ background: brandDraft.primary_color, color: "white" }}><p className="text-xs opacity-75">Brand preview</p><p className="mt-2 text-xl font-semibold">A clear, consistent Jules AI deliverable</p><span className="mt-4 block h-1 w-16 rounded" style={{ background: brandDraft.accent_color }} /></div>
          {brandDraft.can_manage ? <div><Button onClick={() => props.onSaveBrandKit(brandDraft)}><Save data-icon="inline-start" />Save brand kit</Button></div> : <p className="text-xs text-muted-foreground">Only organization owners and admins can change the brand kit.</p>}
        </div>
      </section>
      <Separator className="my-9" />
      <section><div className="flex items-start justify-between gap-4"><div><h2 className="text-base font-semibold">Organizations</h2><p className="mt-1 text-sm text-muted-foreground">Switch workspaces or add another membership.</p></div><Button variant="outline" size="sm" onClick={props.onManageOrganizations}><Plus data-icon="inline-start" />Create or join</Button></div>
        <div className="mt-5 divide-y overflow-hidden rounded-xl border">{props.organizations.map((organization) => <div key={organization.id} className="flex items-center gap-3 p-4"><span className="flex size-9 items-center justify-center rounded-lg bg-muted"><Building2 /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{organization.name}</p><p className="text-xs capitalize text-muted-foreground">{organization.role}</p></div><div className="flex items-center gap-2">{organization.id === props.activeOrganizationId ? <span className="flex items-center gap-1 text-xs font-medium text-primary"><Check className="size-3.5" />Current</span> : <Button variant="outline" size="sm" onClick={() => props.onOrganizationChange(organization.id)}>Switch</Button>}{organization.role !== "owner" ? <AlertDialog><AlertDialogTrigger render={<Button variant="ghost" size="sm" />}>Leave</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Leave {organization.name}?</AlertDialogTitle><AlertDialogDescription>You will immediately lose access to its chats and company knowledge. You need a new invitation to rejoin.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={() => props.onLeaveOrganization(organization.id)}>Leave organization</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog> : null}</div></div>)}</div>
      </section>
      <Separator className="my-9" />
      <section><h2 className="text-base font-semibold">Your data</h2><p className="mt-1 text-sm text-muted-foreground">Export or delete private conversation data without affecting organization prompts.</p><div className="mt-5 flex flex-wrap gap-2"><Button variant="outline" onClick={() => { const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), note: "Use the API export endpoint for full conversation contents." }, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "jules-ai-conversations.json"; link.click(); URL.revokeObjectURL(link.href) }}><Download data-icon="inline-start" />Export conversations</Button>
        <AlertDialog><AlertDialogTrigger render={<Button variant="destructive" />}><Trash2 data-icon="inline-start" />Delete all conversations</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete all of your conversations?</AlertDialogTitle><AlertDialogDescription>This permanently deletes your chats and temporary attachments in this organization. Shared prompts and other members&apos; data are not affected.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={props.onDeleteAllConversations}>Delete conversations</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
      </div></section>
      <Separator className="my-9" />
      <section><h2 className="text-base font-semibold text-destructive">Delete account</h2><p className="mt-1 text-sm text-muted-foreground">Permanently remove your private data and organization memberships. Owners must transfer or delete their organizations first.</p><AlertDialog><AlertDialogTrigger render={<Button className="mt-5" variant="destructive" />}><Trash2 data-icon="inline-start" />Delete personal account</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete your personal account?</AlertDialogTitle><AlertDialogDescription>This removes your private chats, attachments, settings, favorites, and memberships. Shared prompts and audit history remain with anonymized attribution.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={props.onDeleteAccount}>Delete account</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog></section>
    </div></div>
  </section>
}
