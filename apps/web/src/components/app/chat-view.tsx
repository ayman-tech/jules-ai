"use client"

import dynamic from "next/dynamic"
import Image from "next/image"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"
import { AlertTriangle, Ban, BookOpen, Brain, Copy, Download, ExternalLink, Eye, FilePlus2, FileText, FileType2, Globe2, Menu, Paperclip, Presentation, RefreshCw, RotateCcw, Save, Send, Square, Trash2, X } from "lucide-react"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupTextarea } from "@/components/ui/input-group"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Textarea } from "@/components/ui/textarea"
import { julesApi } from "@/lib/api"
import type { Artifact, ArtifactRequest, Attachment, Citation, Conversation, Effort, KnowledgeBase, Message, ModelOption } from "@/lib/types"

const MessageMarkdown = dynamic(() => import("@/components/app/message-markdown"), { loading: () => <div className="flex flex-col gap-2"><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-3/5" /></div> })

interface ChatViewProps {
  conversation: Conversation
  organizationId: string
  messages: Message[]
  models: ModelOption[]
  draft: string
  effort: Effort
  model: string
  knowledgeBases: KnowledgeBase[]
  selectedKnowledgeBaseIds: string[]
  webSearchEnabled: boolean
  artifactRequest?: ArtifactRequest
  pendingAttachments: Attachment[]
  streaming: boolean
  onDraftChange: (value: string) => void
  onEffortChange: (value: Effort) => void
  onModelChange: (value: string) => void
  onKnowledgeBaseIdsChange: (ids: string[]) => void
  onWebSearchChange: (enabled: boolean) => void
  onArtifactRequestChange: (request?: ArtifactRequest) => void
  onArtifactUpdated: (artifact: Artifact) => void
  onArtifactDeleted: (artifactId: string) => void
  onSend: () => void
  onStop: () => void
  onOpenPrompts: () => void
  onFileSelect: (file: File) => void
  onRemoveAttachment: (id: string) => void
  onOpenMobileNavigation: () => void
  onRegenerate: () => void
  onSaveKnowledge: (message: Message, knowledgeBaseId: string, title: string) => void
  onReportAnswer: (message: Message) => void
}

function formatBytes(bytes: number) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export function ChatView(props: ChatViewProps) {
  const fileInput = useRef<HTMLInputElement>(null)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const [knowledgeSearch, setKnowledgeSearch] = useState("")
  const currentModel = props.models.find((model) => model.id === props.model)
  const visibleKnowledge = useMemo(() => props.knowledgeBases.filter((item) => item.title.toLowerCase().includes(knowledgeSearch.toLowerCase())), [knowledgeSearch, props.knowledgeBases])
  const hasSelectedKnowledge = props.selectedKnowledgeBaseIds.length > 0
  const knowledgeLabel = props.selectedKnowledgeBaseIds.length === props.knowledgeBases.length && props.knowledgeBases.length ? "All knowledge" : props.selectedKnowledgeBaseIds.length === 1 ? props.knowledgeBases.find((item) => item.id === props.selectedKnowledgeBaseIds[0])?.title ?? "1 source" : `${props.selectedKnowledgeBaseIds.length} sources`
  useEffect(() => {
    if (props.streaming) messagesEnd.current?.scrollIntoView({ block: "end" })
  }, [props.messages.length, props.streaming])
  return (
    <section className="flex min-w-0 flex-1 flex-col bg-background">
      <header className="flex h-16 shrink-0 items-center gap-3 border-b px-3 sm:px-5">
        <Button variant="ghost" size="icon-lg" className="lg:hidden" aria-label="Open navigation" onClick={props.onOpenMobileNavigation}><Menu /></Button>
        <h1 className="min-w-0 flex-1 truncate text-sm font-semibold sm:text-base">{props.conversation.title}</h1>
        <div className="hidden items-center gap-2 sm:flex">
          <Select value={props.model} onValueChange={(value) => props.onModelChange(value as string)}><SelectTrigger aria-label="Chat model" className="min-w-40"><SelectValue>{(value: string) => props.models.find((model) => model.id === value)?.display_name ?? value}</SelectValue></SelectTrigger><SelectContent><SelectGroup>{props.models.map((model) => <SelectItem key={model.id} value={model.id}>{model.display_name}</SelectItem>)}</SelectGroup></SelectContent></Select>
          <Select value={props.effort} onValueChange={(value) => props.onEffortChange(value as Effort)} disabled={currentModel ? !currentModel.supports_effort : false}><SelectTrigger aria-label="Chat effort" className="min-w-24"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem></SelectGroup></SelectContent></Select>
        </div>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-8 sm:px-8 sm:py-12">
          {props.messages.length ? props.messages.map((message) => (
            <article key={message.id} className={message.role === "user" ? "ml-auto max-w-[88%] sm:max-w-[82%]" : "max-w-full"}>
              {message.role === "user" ? (
                <div className="rounded-2xl rounded-br-md border bg-secondary/65 px-4 py-3 text-[15px] leading-6">
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.attachments?.map((attachment) => <div key={attachment.id} className="mt-3 flex items-center gap-3 rounded-lg border bg-background p-2.5"><span className="flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary"><FileText /></span><span className="min-w-0"><span className="block truncate text-sm font-medium">{attachment.file_name}</span><span className="block text-xs text-muted-foreground">{formatBytes(attachment.size_bytes)}</span></span></div>)}
                </div>
              ) : (
                <div className="flex gap-3 sm:gap-4">
                  <Avatar className="mt-0.5 size-8 border"><AvatarFallback className="bg-primary text-primary-foreground">J</AvatarFallback></Avatar>
                  <div className="min-w-0 flex-1 text-[15px] leading-7">
                    {message.status === "streaming" && !message.content && !message.artifacts?.length ? <AssistantActivity label={message.activity ?? "Thinking"} /> : <MessageMarkdown content={message.content} />}
                    {message.status === "streaming" && message.content ? <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-primary" aria-label="Streaming response" /> : null}
                    <CitationGroups message={message} organizationId={props.organizationId} />
                    {message.artifacts?.map((artifact) => <ArtifactCard key={artifact.id} artifact={artifact} organizationId={props.organizationId} knowledgeBases={props.knowledgeBases} onUpdated={props.onArtifactUpdated} onDeleted={props.onArtifactDeleted} />)}
                    {message.status !== "streaming" && message.content ? <div className="mt-3 flex items-center gap-1"><Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Copy response" onClick={() => navigator.clipboard.writeText(message.content)} />}><Copy /></TooltipTrigger><TooltipContent>Copy</TooltipContent></Tooltip><Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Regenerate response" onClick={props.onRegenerate} />}><RotateCcw /></TooltipTrigger><TooltipContent>Regenerate</TooltipContent></Tooltip><Tooltip><TooltipTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Report incorrect or outdated answer" onClick={() => props.onReportAnswer(message)} />}><AlertTriangle /></TooltipTrigger><TooltipContent>Report answer</TooltipContent></Tooltip>{message.status === "completed" && props.knowledgeBases.length ? <SaveKnowledge message={message} knowledgeBases={props.knowledgeBases} onSave={props.onSaveKnowledge} /> : null}</div> : null}
                  </div>
                </div>
              )}
            </article>
          )) : <div className="flex min-h-80 flex-col items-center justify-center gap-3 text-center"><Avatar className="size-12"><AvatarFallback className="bg-primary text-primary-foreground">J</AvatarFallback></Avatar><h2 className="text-xl font-semibold">How can Jules AI help?</h2><p className="max-w-md text-sm text-muted-foreground">Start a private conversation inside your organization. You can add temporary files or begin with a shared prompt.</p></div>}
          <div ref={messagesEnd} aria-hidden="true" />
        </div>
      </ScrollArea>
      <div className="shrink-0 bg-background px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] sm:px-6 sm:pb-5">
        <div className="mx-auto w-full max-w-3xl">
          {props.pendingAttachments.length ? <div className="mb-2 flex flex-wrap gap-2">{props.pendingAttachments.map((attachment) => <div key={attachment.id} className="flex items-center gap-2 rounded-lg border bg-muted/40 px-2.5 py-1.5 text-xs"><FileText /><span className="max-w-48 truncate">{attachment.file_name}</span><button aria-label={`Remove ${attachment.file_name}`} onClick={() => props.onRemoveAttachment(attachment.id)}><X /></button></div>)}</div> : null}
          {props.streaming ? <div className="mb-2 flex justify-center"><Button variant="outline" onClick={props.onStop}><Square data-icon="inline-start" />Stop</Button></div> : null}
          <InputGroup className="min-h-28 rounded-xl bg-background shadow-sm">
            <InputGroupTextarea value={props.draft} onChange={(event) => props.onDraftChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); props.onSend() } }} placeholder="Ask Jules AI anything" className="min-h-16 px-3 pt-3 text-[15px]" aria-label="Message Jules AI" />
            <InputGroupAddon align="block-end" className="justify-between px-2 pb-2">
              <div className="flex items-center gap-1">
                <input ref={fileInput} type="file" className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) props.onFileSelect(file); event.target.value = "" }} accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.txt,.md,image/png,image/jpeg,image/webp" />
                <Tooltip><TooltipTrigger render={<InputGroupButton size="icon-sm" aria-label="Attach file" onClick={() => fileInput.current?.click()} />}><Paperclip /></TooltipTrigger><TooltipContent>Attach file</TooltipContent></Tooltip>
                <Tooltip><TooltipTrigger render={<InputGroupButton size="icon-sm" aria-label="Open prompt library" onClick={props.onOpenPrompts} />}><BookOpen /></TooltipTrigger><TooltipContent>Prompt library</TooltipContent></Tooltip>
                <DropdownMenu><DropdownMenuTrigger render={<InputGroupButton className={props.artifactRequest ? "w-auto gap-1.5 bg-primary px-2 text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground" : "w-auto gap-1.5 px-2"} aria-label={props.artifactRequest ? `Generate ${props.artifactRequest.format.toUpperCase()}` : "Generate editable file"} aria-pressed={Boolean(props.artifactRequest)} />}><FilePlus2 /><span className="hidden text-xs sm:inline">{props.artifactRequest ? `.${props.artifactRequest.format}` : "Create"}</span></DropdownMenuTrigger><DropdownMenuContent align="start" className="w-64"><DropdownMenuLabel>Create an editable file</DropdownMenuLabel><DropdownMenuItem onClick={() => props.onArtifactRequestChange({ format: "docx", template_id: "auto", use_brand_kit: true })}><FileType2 />Document (.docx)</DropdownMenuItem><DropdownMenuItem onClick={() => props.onArtifactRequestChange({ format: "pptx", template_id: "auto", use_brand_kit: true })}><Presentation />Presentation (.pptx)</DropdownMenuItem>{props.artifactRequest ? <><DropdownMenuSeparator /><DropdownMenuItem onClick={() => props.onArtifactRequestChange(undefined)}><X />Answer in chat instead</DropdownMenuItem></> : null}</DropdownMenuContent></DropdownMenu>
                <DropdownMenu><DropdownMenuTrigger render={<InputGroupButton className={hasSelectedKnowledge ? "w-auto gap-1.5 bg-primary px-2 text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground" : "w-auto gap-1.5 px-2"} aria-label={`Knowledge sources: ${knowledgeLabel}`} aria-pressed={hasSelectedKnowledge} />}><Brain /><span className="hidden text-xs sm:inline">{knowledgeLabel}</span></DropdownMenuTrigger><DropdownMenuContent align="start" className="w-72"><DropdownMenuLabel>Company knowledge</DropdownMenuLabel><div className="px-1.5 pb-1"><Input value={knowledgeSearch} onChange={(event) => setKnowledgeSearch(event.target.value)} placeholder="Search knowledge bases" className="h-8" onKeyDown={(event) => event.stopPropagation()} /></div><div className="flex gap-1 px-1 pb-1"><Button variant="ghost" size="xs" onClick={() => props.onKnowledgeBaseIdsChange(props.knowledgeBases.map((item) => item.id))}>Select all</Button><Button variant="ghost" size="xs" onClick={() => props.onKnowledgeBaseIdsChange([])}>Clear</Button></div><DropdownMenuSeparator />{visibleKnowledge.map((item) => <DropdownMenuCheckboxItem key={item.id} checked={props.selectedKnowledgeBaseIds.includes(item.id)} onCheckedChange={(checked) => props.onKnowledgeBaseIdsChange(checked ? [...props.selectedKnowledgeBaseIds, item.id] : props.selectedKnowledgeBaseIds.filter((id) => id !== item.id))}>{item.title}</DropdownMenuCheckboxItem>)}{!visibleKnowledge.length ? <DropdownMenuItem disabled>No knowledge bases found</DropdownMenuItem> : null}</DropdownMenuContent></DropdownMenu>
                <Tooltip><TooltipTrigger render={<InputGroupButton size="icon-sm" aria-label={props.webSearchEnabled ? "Disable web search" : "Enable web search"} aria-pressed={props.webSearchEnabled} className={props.webSearchEnabled ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground" : ""} onClick={() => props.onWebSearchChange(!props.webSearchEnabled)} />}><Globe2 /></TooltipTrigger><TooltipContent>{props.webSearchEnabled ? "Web search on" : "Web search off"}</TooltipContent></Tooltip>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="hidden items-center gap-1.5 sm:flex"><Select value={props.model} onValueChange={(value) => props.onModelChange(value as string)}><SelectTrigger aria-label="Composer model" size="sm" className="max-w-40"><SelectValue>{(value: string) => props.models.find((model) => model.id === value)?.display_name ?? value}</SelectValue></SelectTrigger><SelectContent><SelectGroup>{props.models.map((model) => <SelectItem key={model.id} value={model.id}>{model.display_name}</SelectItem>)}</SelectGroup></SelectContent></Select><Select value={props.effort} onValueChange={(value) => props.onEffortChange(value as Effort)}><SelectTrigger aria-label="Composer effort" size="sm"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem></SelectGroup></SelectContent></Select></div>
                <div className="sm:hidden"><Select value={props.effort} onValueChange={(value) => props.onEffortChange(value as Effort)}><SelectTrigger aria-label="Composer effort" size="sm"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem></SelectGroup></SelectContent></Select></div>
                <Button size="icon-lg" aria-label="Send message" disabled={!props.draft.trim() || props.streaming} onClick={props.onSend}><Send /></Button>
              </div>
            </InputGroupAddon>
          </InputGroup>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">Jules AI can make mistakes. Verify important business decisions.</p>
        </div>
      </div>
    </section>
  )
}

function AssistantActivity({ label }: { label: string }) {
  return <div role="status" aria-live="polite" className="flex min-h-7 items-center gap-2 text-sm font-medium text-muted-foreground">
    <span>{label}</span>
    <span aria-hidden="true" className="flex items-center gap-1 pt-1">
      <span className="size-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-primary" />
    </span>
  </div>
}

function ArtifactCard({ artifact, organizationId, knowledgeBases, onUpdated, onDeleted }: { artifact: Artifact; organizationId: string; knowledgeBases: KnowledgeBase[]; onUpdated: (artifact: Artifact) => void; onDeleted: (artifactId: string) => void }) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewUrls, setPreviewUrls] = useState<string[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [revisionOpen, setRevisionOpen] = useState(false)
  const [revision, setRevision] = useState("")
  const [saveOpen, setSaveOpen] = useState(false)
  const [knowledgeBaseId, setKnowledgeBaseId] = useState(knowledgeBases[0]?.id ?? "")
  const [selectedVersionOverride, setSelectedVersionOverride] = useState<number | null>(null)
  const selectedVersion = selectedVersionOverride ?? artifact.current_version
  const version = artifact.versions.find((item) => item.version_number === selectedVersion) ?? artifact.version
  const working = ["queued", "planning", "rendering", "validating"].includes(artifact.status)
  const statusLabel = artifact.status === "queued" ? "Queued" : artifact.status === "planning" ? "Planning content" : artifact.status === "rendering" ? "Building file" : artifact.status === "validating" ? "Validating layout" : artifact.status === "ready" ? "Ready" : artifact.status === "failed" ? "Failed" : "Cancelled"

  useEffect(() => () => { previewUrls.forEach((url) => URL.revokeObjectURL(url)) }, [previewUrls])

  async function download() {
    if (!version) return
    try {
      const blob = await julesApi.artifactBlob(organizationId, artifact.id, version.version_number)
      const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = version.file_name ?? `${artifact.title}.${artifact.format}`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (error) { toast.error(error instanceof Error ? error.message : "Download failed") }
  }

  async function openPreview() {
    if (!version?.preview_count) return
    setPreviewOpen(true); setPreviewLoading(true)
    previewUrls.forEach((url) => URL.revokeObjectURL(url)); setPreviewUrls([])
    try {
      const blobs = await Promise.all(Array.from({ length: version.preview_count }, (_, index) => julesApi.artifactPreviewBlob(organizationId, artifact.id, index + 1, version.version_number)))
      setPreviewUrls(blobs.map((blob) => URL.createObjectURL(blob)))
    } catch { toast.error("Preview is unavailable. The editable file can still be downloaded.") }
    finally { setPreviewLoading(false) }
  }

  async function revise() {
    if (!revision.trim()) return
    try { const next = await julesApi.reviseArtifact(organizationId, artifact.id, revision.trim()); setSelectedVersionOverride(null); onUpdated(next); setRevision(""); setRevisionOpen(false); toast.success("Revision queued") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Revision could not be queued") }
  }

  async function saveToKnowledge() {
    if (!knowledgeBaseId) return
    try { await julesApi.saveArtifactToKnowledge(organizationId, artifact.id, knowledgeBaseId, artifact.title); setSaveOpen(false); toast.success("File queued for knowledge ingestion") }
    catch (error) { toast.error(error instanceof Error ? error.message : "File could not be saved to knowledge") }
  }

  return <div className="mt-4 overflow-hidden rounded-xl border bg-background shadow-sm">
    <div className="flex items-start gap-3 p-4"><span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">{artifact.format === "pptx" ? <Presentation /> : <FileType2 />}</span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="truncate font-medium leading-5">{artifact.title}</p><Badge variant={artifact.status === "ready" ? "secondary" : artifact.status === "failed" ? "destructive" : "outline"}>{statusLabel}</Badge></div><p className="mt-1 text-xs text-muted-foreground">Editable {artifact.format.toUpperCase()} · {artifact.template_id.replaceAll("-", " ")}{version?.size_bytes ? ` · ${formatBytes(version.size_bytes)}` : ""}</p>{working ? <Progress className="mt-3" value={artifact.progress} aria-label={`${statusLabel}: ${artifact.progress}%`} /> : null}{artifact.error ? <p className="mt-2 text-xs text-destructive">{artifact.error}</p> : null}</div></div>
    {artifact.versions.length > 1 ? <div className="border-t px-4 py-2"><Select value={String(selectedVersion)} onValueChange={(value) => setSelectedVersionOverride(Number(value))}><SelectTrigger size="sm" className="w-36" aria-label="Artifact version"><SelectValue>{(value: string) => `Version ${value}`}</SelectValue></SelectTrigger><SelectContent><SelectGroup>{artifact.versions.map((item) => <SelectItem key={item.id} value={String(item.version_number)}>Version {item.version_number}</SelectItem>)}</SelectGroup></SelectContent></Select></div> : null}
    <div className="flex flex-wrap gap-2 border-t bg-muted/20 px-4 py-3">
      {version?.status === "ready" ? <><Button variant="outline" size="sm" onClick={() => void download()}><Download data-icon="inline-start" />Download</Button><Button variant="outline" size="sm" disabled={!version.preview_count} onClick={() => void openPreview()}><Eye data-icon="inline-start" />Preview</Button></> : null}
      {artifact.status === "ready" && selectedVersion === artifact.current_version ? <Button variant="outline" size="sm" onClick={() => setRevisionOpen(true)}><RefreshCw data-icon="inline-start" />Revise</Button> : null}
      {artifact.status === "ready" && knowledgeBases.length ? <Button variant="outline" size="sm" onClick={() => setSaveOpen(true)}><Brain data-icon="inline-start" />Save to Knowledge</Button> : null}
      {working ? <Button variant="ghost" size="sm" onClick={async () => { try { onUpdated(await julesApi.cancelArtifact(organizationId, artifact.id)) } catch (error) { toast.error(error instanceof Error ? error.message : "Could not cancel") } }}><Ban data-icon="inline-start" />Cancel</Button> : null}
      {["failed", "cancelled"].includes(artifact.status) ? <Button variant="outline" size="sm" onClick={async () => { try { onUpdated(await julesApi.retryArtifact(organizationId, artifact.id)) } catch (error) { toast.error(error instanceof Error ? error.message : "Could not retry") } }}><RotateCcw data-icon="inline-start" />Retry</Button> : null}
      <AlertDialog><AlertDialogTrigger render={<Button variant="ghost" size="sm" className="ml-auto text-destructive" />}><Trash2 data-icon="inline-start" />Delete</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete this generated file?</AlertDialogTitle><AlertDialogDescription>Every saved version and preview will be permanently removed.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={async () => { try { await julesApi.deleteArtifact(organizationId, artifact.id); onDeleted(artifact.id) } catch (error) { toast.error(error instanceof Error ? error.message : "Could not delete file") } }}>Delete file</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </div>
    <Dialog open={previewOpen} onOpenChange={setPreviewOpen}><DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto"><DialogHeader><DialogTitle>{artifact.title}</DialogTitle><DialogDescription>Version {version?.version_number} · {artifact.format.toUpperCase()} preview</DialogDescription></DialogHeader>{previewLoading ? <div className="grid gap-3"><Skeleton className="h-72 w-full" /><Skeleton className="h-72 w-full" /></div> : <div className="grid gap-4">{previewUrls.map((url, index) => <div key={url} className="overflow-hidden rounded-lg border bg-white"><Image src={url} alt={`${artifact.title} preview ${index + 1}`} width={1400} height={900} unoptimized className="h-auto w-full" /></div>)}</div>}</DialogContent></Dialog>
    <Dialog open={revisionOpen} onOpenChange={setRevisionOpen}><DialogContent><DialogHeader><DialogTitle>Revise this file</DialogTitle><DialogDescription>Describe the changes. Jules will preserve the current version and create version {artifact.current_version + 1}.</DialogDescription></DialogHeader><Textarea value={revision} onChange={(event) => setRevision(event.target.value)} placeholder={artifact.format === "pptx" ? "For example: shorten slide 3 and make the closing recommendation more direct." : "For example: add a weekly checklist and shorten the introduction."} className="min-h-28" /><DialogFooter><Button onClick={() => void revise()} disabled={!revision.trim()}>Create revision</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={saveOpen} onOpenChange={setSaveOpen}><DialogContent><DialogHeader><DialogTitle>Save file to Knowledge</DialogTitle><DialogDescription>This makes the generated file available through the selected knowledge base after ingestion.</DialogDescription></DialogHeader><Select value={knowledgeBaseId} onValueChange={(value) => setKnowledgeBaseId(value as string)}><SelectTrigger className="w-full"><SelectValue placeholder="Choose a knowledge base" /></SelectTrigger><SelectContent><SelectGroup>{knowledgeBases.map((item) => <SelectItem key={item.id} value={item.id}>{item.title}</SelectItem>)}</SelectGroup></SelectContent></Select><DialogFooter><Button onClick={() => void saveToKnowledge()} disabled={!knowledgeBaseId}>Save to Knowledge</Button></DialogFooter></DialogContent></Dialog>
  </div>
}

function CitationGroups({ message, organizationId }: { message: Message; organizationId: string }) {
  const company = message.citations?.filter((item) => item.source_type === "company") ?? []
  const web = message.citations?.filter((item) => item.source_type === "web") ?? []
  if (!company.length && !web.length && !message.grounding_status) return null
  return <div className="mt-4 space-y-3 rounded-xl border bg-muted/20 p-3 text-sm leading-5">{company.length ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Company sources</p><div className="flex flex-wrap gap-2">{company.map((source, index) => <CompanySource key={source.id ?? `${source.title}-${index}`} source={source} organizationId={organizationId} />)}</div></div> : null}{web.length ? <div><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Web sources</p><div className="flex flex-col gap-1">{web.map((source, index) => <a key={source.id ?? `${source.url}-${index}`} href={source.url ?? "#"} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-primary hover:underline"><Globe2 className="size-3.5" /><span className="truncate">{source.title}</span><ExternalLink className="size-3" /></a>)}</div></div> : null}<p className="text-xs text-muted-foreground">Grounding: {(message.grounding_status ?? "pending").replaceAll("_", " ")}</p></div>
}

function CompanySource({ source, organizationId }: { source: Citation; organizationId: string }) {
  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState<{ title: string; content: string; page_number?: number | null; version?: number | null; kind: string } | null>(null)
  async function show() { setOpen(true); if (source.chunk_id) setPreview(await julesApi.sourcePreview(organizationId, source.chunk_id).catch(() => null)) }
  async function openOriginal() {
    if (!source.document_id || !source.version_id) return
    const blob = await julesApi.knowledgeVersionBlob(organizationId, source.document_id, source.version_id)
    const url = URL.createObjectURL(blob); window.open(url, "_blank", "noopener,noreferrer"); window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger render={<button onClick={() => void show()} className="inline-flex max-w-full items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium hover:bg-secondary/80" />}><Brain className="size-3" /><span className="truncate">{source.title}{source.location ? ` · ${source.location}` : ""}</span></DialogTrigger><DialogContent><DialogHeader><DialogTitle>{source.title}</DialogTitle><DialogDescription>{String(source.metadata?.knowledge_base_title ?? "Company source")}{preview?.version ? ` · version ${preview.version}` : ""}{preview?.page_number ? ` · page ${preview.page_number}` : ""}</DialogDescription></DialogHeader><div className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">{preview?.content ?? "Loading source preview…"}</div><DialogFooter><Button variant="outline" onClick={() => void openOriginal()} disabled={!source.document_id || !source.version_id}>Open original</Button></DialogFooter></DialogContent></Dialog>
}

function SaveKnowledge({ message, knowledgeBases, onSave }: { message: Message; knowledgeBases: KnowledgeBase[]; onSave: (message: Message, knowledgeBaseId: string, title: string) => void }) {
  const [open, setOpen] = useState(false)
  const [knowledgeBaseId, setKnowledgeBaseId] = useState(knowledgeBases[0]?.id ?? "")
  const [title, setTitle] = useState("Chat-derived knowledge")
  return <Dialog open={open} onOpenChange={setOpen}><Tooltip><TooltipTrigger render={<DialogTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Save to knowledge" />} />}><Save /></TooltipTrigger><TooltipContent>Save to Knowledge</TooltipContent></Tooltip><DialogContent><DialogHeader><DialogTitle>Save to Knowledge</DialogTitle><DialogDescription>Edit the title and choose a knowledge base. An owner or admin must approve this before colleagues can retrieve it.</DialogDescription></DialogHeader><div className="grid gap-3"><Input value={title} onChange={(event) => setTitle(event.target.value)} aria-label="Knowledge proposal title" /><select value={knowledgeBaseId} onChange={(event) => setKnowledgeBaseId(event.target.value)} className="h-9 rounded-lg border bg-background px-3 text-sm">{knowledgeBases.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><div className="max-h-44 overflow-y-auto rounded-lg border bg-muted/30 p-3 text-sm">{message.content}</div></div><DialogFooter><Button onClick={() => { onSave(message, knowledgeBaseId, title); setOpen(false) }} disabled={!knowledgeBaseId || !title.trim()}>Submit for review</Button></DialogFooter></DialogContent></Dialog>
}
