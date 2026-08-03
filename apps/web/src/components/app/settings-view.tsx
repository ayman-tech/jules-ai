"use client"

import Image from "next/image"
import { Building2, Check, Download, Eye, FileText, Menu, Plus, Save, Trash2, Upload } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { julesApi } from "@/lib/api"
import type { DocumentTemplateVersion, Effort, ModelOption, Organization, OrganizationDocumentTemplate, UserSettings } from "@/lib/types"

interface SettingsViewProps {
  settings: UserSettings
  documentTemplate: OrganizationDocumentTemplate
  models: ModelOption[]
  organizations: Organization[]
  activeOrganizationId: string
  onOrganizationChange: (id: string) => void
  onManageOrganizations: () => void
  onLeaveOrganization: (id: string) => void
  onSave: (settings: UserSettings) => void
  onUploadDocumentTemplate: (file: File) => void
  onActivateDocumentTemplate: (versionId: string) => void
  onDisableDocumentTemplate: () => void
  onDownloadDocumentTemplate: (version: DocumentTemplateVersion) => void
  onDeleteAllConversations: () => void
  onDeleteAccount: () => void
  onOpenMobileNavigation: () => void
}

export function SettingsView(props: SettingsViewProps) {
  const [draft, setDraft] = useState(props.settings)
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
      <DocumentTemplateSettings {...props} />
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

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function DocumentTemplateSettings(props: SettingsViewProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const template = props.documentTemplate
  const active = template.active_version
  const pending = template.pending_version
  const [previewVersion, setPreviewVersion] = useState<DocumentTemplateVersion | null>(null)
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  useEffect(() => () => { previewUrls.forEach((url) => URL.revokeObjectURL(url)) }, [previewUrls])
  async function preview(version: DocumentTemplateVersion) {
    setPreviewVersion(version); setPreviewLoading(true)
    previewUrls.forEach((url) => URL.revokeObjectURL(url)); setPreviewUrls([])
    try {
      const blobs = await Promise.all(Array.from({ length: version.preview_count }, (_, index) => julesApi.documentTemplatePreviewBlob(props.activeOrganizationId, version.id, index + 1)))
      setPreviewUrls(blobs.map((blob) => URL.createObjectURL(blob)))
    } catch (error) { toast.error(error instanceof Error ? error.message : "Document template preview is unavailable") }
    finally { setPreviewLoading(false) }
  }
  return <><section>
    <div className="flex items-start gap-3"><span className="mt-0.5 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary"><FileText /></span><div><h2 className="text-base font-semibold">Organization document template</h2><p className="mt-1 text-sm text-muted-foreground">Jules uses this Word template for letterhead, margins, headers, footers, fonts, colors, lists, and table styles.</p></div></div>
    <div className="mt-5 grid gap-4 rounded-xl border p-5">
      <div className="rounded-lg bg-muted/45 p-4 text-sm text-muted-foreground"><p className="font-medium text-foreground">Prepare the template in Word</p><p className="mt-1">Put reusable letterhead in the header or footer. Sample body content is removed before Jules adds the generated document. Upload a `.docx` file with one section, up to 15 MB.</p></div>
      {active ? <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center"><span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><FileText /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-medium">{active.file_name}</p><Badge variant={template.enabled ? "secondary" : "outline"}>{template.enabled ? "Active" : "Disabled"}</Badge></div><p className="mt-1 text-xs text-muted-foreground">Version {active.version_number} · {formatBytes(active.size_bytes)} · validated</p></div><div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" disabled={!active.preview_count} onClick={() => void preview(active)}><Eye data-icon="inline-start" />Preview</Button>{template.can_manage ? <Button variant="outline" size="sm" onClick={() => props.onDownloadDocumentTemplate(active)}><Download data-icon="inline-start" />Download</Button> : null}</div></div> : <p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">No validated organization template is active. Jules will use its built-in document styling.</p>}
      {pending ? <div className="rounded-lg border border-primary/25 bg-primary/5 p-4"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-medium">{pending.file_name}</p><Badge variant="outline">{pending.status === "queued" ? "Waiting to validate" : "Validating"}</Badge></div><p className="mt-1 text-xs text-muted-foreground">The current template remains active until this replacement passes every check.</p><Progress className="mt-3" value={pending.progress} aria-label={`Template validation: ${pending.progress}%`} /></div> : null}
      {template.versions.find((version) => version.status === "failed") ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm"><p className="font-medium text-destructive">The latest template could not be activated</p><p className="mt-1 text-xs text-muted-foreground">{template.versions.find((version) => version.status === "failed")?.error}</p></div> : null}
      {template.can_manage ? <div className="flex flex-wrap gap-2"><input ref={inputRef} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) props.onUploadDocumentTemplate(file); event.target.value = "" }} /><Button onClick={() => inputRef.current?.click()} disabled={Boolean(pending)}><Upload data-icon="inline-start" />{active ? "Replace template" : "Upload template"}</Button>{active && template.enabled ? <Button variant="outline" onClick={props.onDisableDocumentTemplate}>Disable template</Button> : null}{active && !template.enabled ? <Button variant="outline" onClick={() => props.onActivateDocumentTemplate(active.id)}>Enable template</Button> : null}</div> : <p className="text-xs text-muted-foreground">Only organization owners and admins can upload or change the template.</p>}
      {template.can_manage && template.versions.length > 1 ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Version history</p><div className="divide-y overflow-hidden rounded-lg border">{template.versions.map((version) => <div key={version.id} className="flex flex-wrap items-center gap-3 p-3"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">Version {version.version_number} · {version.file_name}</p><p className="mt-0.5 text-xs text-muted-foreground">{formatBytes(version.size_bytes)} · {version.status}</p>{version.error ? <p className="mt-1 text-xs text-destructive">{version.error}</p> : null}</div>{version.status === "ready" ? <><Button variant="ghost" size="sm" disabled={!version.preview_count} onClick={() => void preview(version)}><Eye data-icon="inline-start" />Preview</Button>{version.id !== template.active_version_id ? <Button variant="outline" size="sm" onClick={() => props.onActivateDocumentTemplate(version.id)}>Activate</Button> : null}</> : null}</div>)}</div></div> : null}
    </div>
  </section><Dialog open={Boolean(previewVersion)} onOpenChange={(open) => { if (!open) setPreviewVersion(null) }}><DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto"><DialogHeader><DialogTitle>{previewVersion?.file_name}</DialogTitle><DialogDescription>Generated validation sample using organization template version {previewVersion?.version_number}. Sample body content is not retained.</DialogDescription></DialogHeader>{previewLoading ? <p className="py-16 text-center text-sm text-muted-foreground">Loading every preview page…</p> : <div className="grid gap-4">{previewUrls.map((url, index) => <div key={url} className="overflow-hidden rounded-lg border bg-white"><Image src={url} alt={`Document template preview page ${index + 1}`} width={1400} height={1800} unoptimized className="h-auto w-full" /></div>)}</div>}</DialogContent></Dialog></>
}
