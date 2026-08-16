"use client"

import { useDeferredValue, useMemo, useState } from "react"
import { ArrowUpRight, BookOpen, Search, Send, Star } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { extractPromptVariables, fillPromptVariables } from "@/lib/api"
import type { Prompt } from "@/lib/types"

const VARIABLE_LABELS: Record<string, string> = { company_name: "Company name", reporting_period: "Reporting period" }

interface PromptPickerDialogProps {
  open: boolean
  prompts: Prompt[]
  onOpenChange: (open: boolean) => void
  onUsePrompt: (body: string) => boolean | void
  onFavorite: (id: string) => void
  onManagePrompts: () => void
}

export function PromptPickerDialog(props: PromptPickerDialogProps) {
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null)
  const [variables, setVariables] = useState<Record<string, string>>({})

  const visiblePrompts = useMemo(() => {
    const needle = deferredSearch.trim().toLowerCase()
    return props.prompts.filter((prompt) => {
      if (prompt.archived || (favoritesOnly && !prompt.favorite)) return false
      return !needle || `${prompt.title} ${prompt.description ?? ""} ${prompt.tags.join(" ")}`.toLowerCase().includes(needle)
    })
  }, [deferredSearch, favoritesOnly, props.prompts])
  const variableNames = useMemo(() => selectedPrompt ? extractPromptVariables(selectedPrompt.body) : [], [selectedPrompt])
  const variablesComplete = variableNames.every((name) => variables[name]?.trim())

  function selectPrompt(prompt: Prompt) {
    setSelectedPrompt(prompt)
    setVariables(Object.fromEntries(extractPromptVariables(prompt.body).map((name) => [name, ""])))
  }

  function close() {
    props.onOpenChange(false)
    setSearch("")
    setFavoritesOnly(false)
    setSelectedPrompt(null)
    setVariables({})
  }

  function useSelectedPrompt() {
    if (!selectedPrompt || !variablesComplete) return
    if (props.onUsePrompt(fillPromptVariables(selectedPrompt.body, variables)) === false) return
    close()
  }

  return (
    <Dialog open={props.open} onOpenChange={(open) => { if (open) props.onOpenChange(true); else close() }}>
      <DialogContent className="flex max-h-[min(760px,88vh)] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Choose a prompt</DialogTitle>
          <DialogDescription>Preview a shared prompt and insert it without leaving this conversation.</DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-4 md:grid md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="flex min-h-0 flex-col rounded-xl border">
            <div className="flex items-center gap-2 border-b p-3">
              <Search className="size-4 shrink-0 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search prompts" aria-label="Search prompt picker" className="h-8 border-0 px-0 shadow-none focus-visible:ring-0" />
              <Button type="button" variant={favoritesOnly ? "secondary" : "ghost"} size="icon-sm" aria-label={favoritesOnly ? "Show all prompts" : "Show favorite prompts"} aria-pressed={favoritesOnly} onClick={() => setFavoritesOnly((current) => !current)}><Star className={favoritesOnly ? "fill-primary text-primary" : ""} /></Button>
            </div>
            <ScrollArea className="h-64 md:h-[420px]">
              <div className="divide-y">
                {visiblePrompts.map((prompt) => <div key={prompt.id} className={selectedPrompt?.id === prompt.id ? "flex items-start bg-muted/60" : "flex items-start"}>
                  <button type="button" className="min-w-0 flex-1 px-3 py-3 text-left hover:bg-muted/40" aria-label={`Select prompt ${prompt.title}`} aria-pressed={selectedPrompt?.id === prompt.id} onClick={() => selectPrompt(prompt)}>
                    <span className="block truncate text-sm font-medium">{prompt.title}</span>
                    <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">{prompt.description || prompt.body}</span>
                  </button>
                  <Button type="button" variant="ghost" size="icon-sm" className="mr-2 mt-2 shrink-0" aria-label={prompt.favorite ? `Remove ${prompt.title} from favorites` : `Add ${prompt.title} to favorites`} onClick={() => props.onFavorite(prompt.id)}><Star className={prompt.favorite ? "fill-primary text-primary" : "text-muted-foreground"} /></Button>
                </div>)}
                {!visiblePrompts.length ? <div className="flex flex-col items-center gap-2 px-4 py-12 text-center"><BookOpen className="text-muted-foreground" /><p className="text-sm font-medium">No prompts found</p><p className="text-xs text-muted-foreground">Try another search or show all prompts.</p></div> : null}
              </div>
            </ScrollArea>
          </div>
          <div className="min-h-48 rounded-xl border bg-muted/15 p-4">
            {selectedPrompt ? <div className="flex h-full flex-col">
              <div><h3 className="font-semibold">{selectedPrompt.title}</h3>{selectedPrompt.description ? <p className="mt-1 text-sm text-muted-foreground">{selectedPrompt.description}</p> : null}</div>
              {selectedPrompt.tags.length ? <div className="mt-3 flex flex-wrap gap-1.5">{selectedPrompt.tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
              <ScrollArea className="mt-4 max-h-52 flex-1 rounded-lg border bg-background"><p className="whitespace-pre-wrap p-3 text-sm leading-6">{selectedPrompt.body}</p></ScrollArea>
              {variableNames.length ? <FieldGroup className="mt-4">{variableNames.map((name) => <Field key={name}><FieldLabel htmlFor={`picker-${name}`}>{VARIABLE_LABELS[name] ?? name.replaceAll("_", " ")}</FieldLabel><Input id={`picker-${name}`} value={variables[name] ?? ""} onChange={(event) => setVariables((current) => ({ ...current, [name]: event.target.value }))} /></Field>)}</FieldGroup> : null}
            </div> : <div className="flex h-full min-h-52 flex-col items-center justify-center gap-2 text-center"><BookOpen className="text-muted-foreground" /><p className="text-sm font-medium">Select a prompt to preview it</p><p className="max-w-xs text-xs leading-5 text-muted-foreground">Your current conversation and draft remain unchanged until you choose Use prompt.</p></div>}
          </div>
        </div>
        <DialogFooter className="sm:justify-between">
          <Button type="button" variant="ghost" onClick={() => { close(); props.onManagePrompts() }}><ArrowUpRight data-icon="inline-start" />Manage prompts</Button>
          <Button type="button" disabled={!selectedPrompt || !variablesComplete} onClick={useSelectedPrompt}><Send data-icon="inline-start" />Use prompt</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
