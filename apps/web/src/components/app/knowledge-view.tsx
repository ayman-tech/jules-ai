"use client"

import { useMemo, useRef, useState } from "react"
import { Archive, FileText, Menu, Plus, Search, Upload, Users } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { KnowledgeBase, Member, Role } from "@/lib/types"

interface KnowledgeViewProps {
  knowledgeBases: KnowledgeBase[]
  activeKnowledgeBase?: KnowledgeBase
  members: Member[]
  role: Role
  onSelect: (id: string) => void
  onCreate: (title: string, description: string) => void
  onUpdate: (knowledgeBaseId: string, title: string, description: string) => void
  onUpload: (knowledgeBaseId: string, files: File[]) => void
  onUpdateAccess: (knowledgeBaseId: string, userIds: string[], reason: string) => void
  onArchive: (knowledgeBaseId: string) => void
  onOpenMobileNavigation: () => void
}

function formatBytes(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function KnowledgeSettings({ knowledgeBase, onUpdate, onArchive }: {
  knowledgeBase: KnowledgeBase
  onUpdate: (knowledgeBaseId: string, title: string, description: string) => void
  onArchive: (knowledgeBaseId: string) => void
}) {
  const [title, setTitle] = useState(knowledgeBase.title)
  const [description, setDescription] = useState(knowledgeBase.description)
  const changed = title.trim() !== knowledgeBase.title || description.trim() !== knowledgeBase.description

  return <div className="rounded-xl border p-6">
    <h3 className="font-medium">Knowledge base settings</h3>
    <p className="mt-1 text-sm text-muted-foreground">Only owners and admins can rename, archive, or manage access. Changes are audited.</p>
    <div className="mt-6 grid max-w-2xl gap-4">
      <div className="grid gap-2"><Label htmlFor="knowledge-settings-title">Name</Label><Input id="knowledge-settings-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={180} /></div>
      <div className="grid gap-2"><Label htmlFor="knowledge-settings-description">Description</Label><Textarea id="knowledge-settings-description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={4000} rows={5} /></div>
      <div><Button onClick={() => onUpdate(knowledgeBase.id, title.trim(), description.trim())} disabled={!title.trim() || !changed}>Save changes</Button></div>
    </div>
    <div className="mt-8 border-t pt-6"><h4 className="text-sm font-medium">Danger zone</h4><Button variant="destructive" className="mt-3" onClick={() => onArchive(knowledgeBase.id)}><Archive data-icon="inline-start" />Archive knowledge base</Button></div>
  </div>
}

export function KnowledgeView(props: KnowledgeViewProps) {
  const [search, setSearch] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [accessIds, setAccessIds] = useState<string[] | null>(null)
  const [accessReason, setAccessReason] = useState("")
  const fileInput = useRef<HTMLInputElement>(null)
  const canManage = props.role === "owner" || props.role === "admin"
  const filtered = useMemo(() => props.knowledgeBases.filter((item) => `${item.title} ${item.description}`.toLowerCase().includes(search.toLowerCase())), [props.knowledgeBases, search])
  const selectedAccess = accessIds ?? props.activeKnowledgeBase?.members?.map((member) => member.id) ?? []

  function submitCreate() {
    if (!title.trim()) return
    props.onCreate(title.trim(), description.trim()); setTitle(""); setDescription(""); setCreateOpen(false)
  }

  function acceptFiles(files: FileList | null) {
    if (props.activeKnowledgeBase && files?.length) props.onUpload(props.activeKnowledgeBase.id, Array.from(files))
  }

  return <section className="flex min-w-0 flex-1 bg-background">
    <aside className={cn("w-full border-r sm:w-80", props.activeKnowledgeBase && "hidden sm:block")}>
      <header className="flex h-16 items-center gap-2 border-b px-3"><Button variant="ghost" size="icon-lg" className="lg:hidden" aria-label="Open navigation" onClick={props.onOpenMobileNavigation}><Menu /></Button><h1 className="flex-1 font-semibold">Knowledge</h1>{canManage ? <Dialog open={createOpen} onOpenChange={setCreateOpen}><DialogTrigger render={<Button size="icon-sm" aria-label="Create knowledge base" />}><Plus /></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Create knowledge base</DialogTitle><DialogDescription>Create a private source space, then choose who can access it.</DialogDescription></DialogHeader><div className="grid gap-4"><div className="grid gap-2"><Label htmlFor="kb-title">Title</Label><Input id="kb-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Legal" /></div><div className="grid gap-2"><Label htmlFor="kb-description">Description</Label><Textarea id="kb-description" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Policies, decisions, and established practices for the legal team." /></div></div><DialogFooter><Button onClick={submitCreate} disabled={!title.trim()}>Create</Button></DialogFooter></DialogContent></Dialog> : null}</header>
      <div className="p-3"><div className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search knowledge" className="pl-9" /></div></div>
      <div className="space-y-1 px-2">{filtered.map((item) => <button key={item.id} onClick={() => props.onSelect(item.id)} className={cn("w-full rounded-xl p-3 text-left hover:bg-muted", props.activeKnowledgeBase?.id === item.id && "bg-muted")}><span className="block text-sm font-medium">{item.title}</span><span className="mt-1 line-clamp-2 block text-xs text-muted-foreground">{item.description || "No description"}</span><span className="mt-2 block text-xs text-muted-foreground">{item.document_count} files · {item.member_count} people</span></button>)}</div>
    </aside>
    {props.activeKnowledgeBase ? <div className="min-w-0 flex-1 overflow-y-auto"><header className="flex min-h-16 items-center gap-3 border-b px-4 sm:px-6"><Button variant="ghost" size="sm" className="sm:hidden" onClick={() => props.onSelect("")}>Back</Button><div className="min-w-0 flex-1"><h2 className="truncate font-semibold">{props.activeKnowledgeBase.title}</h2><p className="truncate text-xs text-muted-foreground">{props.activeKnowledgeBase.description}</p></div>{canManage ? <Button variant="ghost" size="icon-sm" aria-label="Archive knowledge base" onClick={() => props.onArchive(props.activeKnowledgeBase!.id)}><Archive /></Button> : null}</header>
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8"><Tabs defaultValue="files"><TabsList variant="line"><TabsTrigger value="files">Files</TabsTrigger><TabsTrigger value="conflicts">Conflicts</TabsTrigger>{canManage ? <TabsTrigger value="access">Access</TabsTrigger> : null}{canManage ? <TabsTrigger value="settings">Settings</TabsTrigger> : null}</TabsList>
        <TabsContent value="files" className="pt-6"><input ref={fileInput} type="file" multiple className="sr-only" accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.md" onChange={(event) => { acceptFiles(event.target.files); event.target.value = "" }} /><button className="flex w-full flex-col items-center rounded-xl border border-dashed p-8 text-center hover:bg-muted/30" onClick={() => fileInput.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); acceptFiles(event.dataTransfer.files) }}><Upload className="mb-3 size-6 text-primary" /><span className="text-sm font-medium">Drop files here or browse</span><span className="mt-1 text-xs text-muted-foreground">PDF, DOCX, PPTX, XLSX, CSV, TXT, or Markdown · up to 50 MB each</span></button><div className="mt-6 divide-y rounded-xl border">{props.activeKnowledgeBase.documents?.length ? props.activeKnowledgeBase.documents.map((document) => { const version = document.versions[0]; return <div key={document.id} className="flex items-center gap-3 p-4"><span className="rounded-lg bg-primary/10 p-2 text-primary"><FileText /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{document.title}</p><p className="text-xs text-muted-foreground">Version {document.current_version}{version ? ` · ${formatBytes(version.size_bytes)}` : ""}</p></div>{version ? <Badge variant={version.extraction_status === "ready" ? "secondary" : "outline"}>{version.extraction_status}</Badge> : null}</div> }) : <div className="p-8 text-center text-sm text-muted-foreground">No documents have been uploaded yet.</div>}</div></TabsContent>
        <TabsContent value="conflicts" className="pt-6"><div className="rounded-xl border p-6"><h3 className="font-medium">Conflict review</h3><p className="mt-1 text-sm text-muted-foreground">Open duplicate or contradictory claims appear here and in Knowledge Review. Jules discloses unresolved conflicts in answers.</p></div></TabsContent>
        {canManage ? <TabsContent value="access" className="pt-6"><div className="space-y-3">{props.members.map((member) => <div key={member.id} className="flex items-center gap-3 rounded-xl border p-3"><span className="rounded-lg bg-muted p-2"><Users /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{member.display_name}</p><p className="truncate text-xs text-muted-foreground">{member.email}</p></div><Switch checked={selectedAccess.includes(member.id)} onCheckedChange={(checked) => setAccessIds(checked ? [...selectedAccess, member.id] : selectedAccess.filter((id) => id !== member.id))} aria-label={`Access for ${member.display_name}`} /></div>)}<Label htmlFor="access-reason">Audit reason</Label><Input id="access-reason" value={accessReason} onChange={(event) => setAccessReason(event.target.value)} placeholder="Why is access changing?" /><Button onClick={() => props.onUpdateAccess(props.activeKnowledgeBase!.id, selectedAccess, accessReason)}>Save access</Button></div></TabsContent> : null}
        {canManage ? <TabsContent value="settings" className="pt-6"><KnowledgeSettings key={props.activeKnowledgeBase.id} knowledgeBase={props.activeKnowledgeBase} onUpdate={props.onUpdate} onArchive={props.onArchive} /></TabsContent> : null}
      </Tabs></div>
    </div> : <div className="hidden flex-1 items-center justify-center text-sm text-muted-foreground sm:flex">Select a knowledge base to view its files.</div>}
  </section>
}
