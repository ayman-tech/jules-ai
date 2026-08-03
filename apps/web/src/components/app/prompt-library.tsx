"use client"

import { useDeferredValue, useMemo, useState } from "react"
import { Archive, BookOpen, ChevronDown, ChevronRight, Edit3, History, Menu, Plus, Search, Send, Star } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { extractPromptVariables, fillPromptVariables } from "@/lib/api"
import type { Prompt, PromptVersion, Role } from "@/lib/types"

interface PromptLibraryProps {
  prompts: Prompt[]
  role: Role
  onUsePrompt: (body: string) => void
  onFavorite: (id: string) => void
  onSave: (prompt: Pick<Prompt, "title" | "description" | "body" | "tags">, id?: string) => void
  onLoadVersions: (prompt: Prompt) => Promise<PromptVersion[]>
  onRestoreVersion: (prompt: Prompt, version: number) => Promise<void>
  onOpenMobileNavigation: () => void
}

const VARIABLE_LABELS: Record<string, string> = { company_name: "Company name", reporting_period: "Reporting period" }

export function PromptLibrary(props: PromptLibraryProps) {
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [filter, setFilter] = useState("all")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [variablePrompt, setVariablePrompt] = useState<Prompt | null>(null)
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<Prompt | null>(null)
  const [historyPrompt, setHistoryPrompt] = useState<Prompt | null>(null)
  const [historyVersions, setHistoryVersions] = useState<PromptVersion[]>([])
  const [form, setForm] = useState({ title: "", description: "", body: "", tags: "" })

  const visible = useMemo(() => props.prompts.filter((prompt) => {
    if (filter === "favorites" && !prompt.favorite) return false
    if (filter === "archived" && !prompt.archived) return false
    if (filter !== "archived" && prompt.archived) return false
    const needle = deferredSearch.trim().toLowerCase()
    return !needle || `${prompt.title} ${prompt.description ?? ""} ${prompt.tags.join(" ")}`.toLowerCase().includes(needle)
  }), [props.prompts, filter, deferredSearch])

  function beginUse(prompt: Prompt) {
    const names = extractPromptVariables(prompt.body)
    if (names.length) { setVariablePrompt(prompt); setVariables(Object.fromEntries(names.map((name) => [name, ""]))) }
    else props.onUsePrompt(prompt.body)
  }

  function openEditor(prompt?: Prompt) {
    setEditing(prompt ?? null)
    setForm(prompt ? { title: prompt.title, description: prompt.description ?? "", body: prompt.body, tags: prompt.tags.join(", ") } : { title: "", description: "", body: "", tags: "" })
    setEditorOpen(true)
  }

  function savePrompt() {
    if (!form.title.trim() || !form.body.trim()) return
    props.onSave({ title: form.title.trim(), description: form.description.trim(), body: form.body.trim(), tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean) }, editing?.id)
    setEditorOpen(false)
  }

  async function openHistory(prompt: Prompt) {
    setHistoryPrompt(prompt)
    setHistoryVersions(await props.onLoadVersions(prompt))
  }

  return (
    <section className="flex min-w-0 flex-1 flex-col bg-background">
      <header className="flex h-16 shrink-0 items-center gap-3 border-b px-3 sm:px-6 lg:hidden"><Button variant="ghost" size="icon-lg" aria-label="Open navigation" onClick={props.onOpenMobileNavigation}><Menu /></Button><span className="font-semibold">Prompt library</span></header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
          <div className="flex items-start justify-between gap-4">
            <div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Prompt library</h1><p className="mt-1.5 text-sm text-muted-foreground">Reusable prompts for everyone at Northstar Advisory.</p></div>
            {props.role !== "member" ? <Button onClick={() => openEditor()}><Plus data-icon="inline-start" />New prompt</Button> : null}
          </div>
          <div className="mt-8 flex max-w-md items-center gap-2"><Search className="text-muted-foreground" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search prompts" aria-label="Search prompts" /></div>
          <Tabs value={filter} onValueChange={(value) => setFilter(value as string)} className="mt-5"><TabsList><TabsTrigger value="all">All</TabsTrigger><TabsTrigger value="favorites">Favorites</TabsTrigger><TabsTrigger value="archived"><Archive />Archived</TabsTrigger></TabsList></Tabs>
          <Separator className="mt-5" />
          <div className="flex flex-col">
            {visible.map((prompt) => {
              const isOpen = expanded === prompt.id
              return <div key={prompt.id} className="border-b">
                <button className="flex w-full items-center gap-3 px-1 py-5 text-left" onClick={() => { if (isOpen) beginUse(prompt); else setExpanded(prompt.id) }} aria-expanded={isOpen}>
                  {isOpen ? <ChevronDown /> : <ChevronRight />}<Star className={prompt.favorite ? "fill-primary text-primary" : "text-muted-foreground"} /><span className="text-[15px] font-medium">{prompt.title}</span>
                </button>
                {isOpen ? <div className="flex flex-col gap-4 pb-6 pl-9 pr-2 sm:pl-16">
                  <p className="text-sm text-muted-foreground">{prompt.description}</p>
                  <div className="flex flex-wrap items-center gap-2">{prompt.tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}<span className="text-xs text-muted-foreground">v{prompt.version_number} · edited {new Date(prompt.updated_at).toLocaleDateString()} by {prompt.last_editor}</span></div>
                  <div className="rounded-lg border bg-muted/25 p-4 text-sm leading-6">{prompt.body}</div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={(event) => { event.stopPropagation(); beginUse(prompt) }}><Send data-icon="inline-start" />Use prompt</Button>
                    <Button variant="ghost" onClick={(event) => { event.stopPropagation(); props.onFavorite(prompt.id) }}><Star data-icon="inline-start" />{prompt.favorite ? "Favorited" : "Favorite"}</Button>
                    {props.role !== "member" ? <Button variant="ghost" onClick={(event) => { event.stopPropagation(); openEditor(prompt) }}><Edit3 data-icon="inline-start" />Edit</Button> : null}
                    <Button variant="ghost" onClick={() => void openHistory(prompt)}><History data-icon="inline-start" />Version history</Button>
                  </div>
                </div> : null}
              </div>
            })}
            {!visible.length ? <div className="flex flex-col items-center gap-3 py-20 text-center"><BookOpen className="text-muted-foreground" /><p className="font-medium">No prompts found</p><p className="text-sm text-muted-foreground">Try a different search or filter.</p></div> : null}
          </div>
        </div>
      </ScrollArea>

      <Dialog open={Boolean(variablePrompt)} onOpenChange={(open) => { if (!open) setVariablePrompt(null) }}>
        <DialogContent className="sm:max-w-lg"><DialogHeader><DialogTitle>Prompt variables</DialogTitle><DialogDescription>Fill in the variables below before using this prompt.</DialogDescription></DialogHeader>
          <FieldGroup>{variablePrompt ? extractPromptVariables(variablePrompt.body).map((name) => <Field key={name}><FieldLabel htmlFor={name}>{VARIABLE_LABELS[name] ?? name.replaceAll("_", " ")}</FieldLabel><Input id={name} value={variables[name] ?? ""} onChange={(event) => setVariables((current) => ({ ...current, [name]: event.target.value }))} placeholder={name === "company_name" ? "Northstar Advisory" : "Q3 2026"} /></Field>) : null}</FieldGroup>
          <DialogFooter showCloseButton><Button disabled={!Object.values(variables).every((value) => value.trim())} onClick={() => { if (variablePrompt) props.onUsePrompt(fillPromptVariables(variablePrompt.body, variables)); setVariablePrompt(null) }}>Insert prompt</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>{editing ? "Edit prompt" : "New prompt"}</DialogTitle><DialogDescription>Shared with every member of Northstar Advisory.</DialogDescription></DialogHeader>
          <FieldGroup><Field><FieldLabel htmlFor="prompt-title">Title</FieldLabel><Input id="prompt-title" value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} /></Field><Field><FieldLabel htmlFor="prompt-description">Description</FieldLabel><Input id="prompt-description" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} /></Field><Field><FieldLabel htmlFor="prompt-body">Prompt</FieldLabel><Textarea id="prompt-body" className="min-h-36" value={form.body} onChange={(event) => setForm((current) => ({ ...current, body: event.target.value }))} /></Field><Field><FieldLabel htmlFor="prompt-tags">Tags</FieldLabel><Input id="prompt-tags" placeholder="Strategy, Leadership" value={form.tags} onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))} /></Field></FieldGroup>
          <DialogFooter showCloseButton><Button disabled={!form.title.trim() || !form.body.trim()} onClick={savePrompt}>{editing ? "Save new version" : "Create prompt"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(historyPrompt)} onOpenChange={(open) => { if (!open) setHistoryPrompt(null) }}>
        <DialogContent className="sm:max-w-xl"><DialogHeader><DialogTitle>Version history</DialogTitle><DialogDescription>Review immutable versions and restore a previous prompt as a new version.</DialogDescription></DialogHeader>
          <div className="max-h-80 overflow-y-auto divide-y rounded-lg border">{historyVersions.map((version) => <div key={version.id} className="flex items-start gap-4 p-4"><div className="min-w-0 flex-1"><p className="text-sm font-medium">Version {version.version_number} · {version.title}</p><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{version.body}</p><p className="mt-2 text-xs text-muted-foreground">{new Date(version.created_at).toLocaleDateString()}</p></div>{historyPrompt && version.version_number !== historyPrompt.version_number && props.role !== "member" ? <Button size="sm" variant="outline" onClick={async () => { await props.onRestoreVersion(historyPrompt, version.version_number); setHistoryPrompt(null) }}>Restore</Button> : <Badge variant="secondary">{version.version_number === historyPrompt?.version_number ? "Current" : "Read only"}</Badge>}</div>)}</div>
        </DialogContent>
      </Dialog>
    </section>
  )
}
