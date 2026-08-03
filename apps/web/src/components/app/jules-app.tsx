"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { AppSidebar } from "@/components/app/app-sidebar"
import { ChatView } from "@/components/app/chat-view"
import { KnowledgeReviewView } from "@/components/app/knowledge-review-view"
import { KnowledgeView } from "@/components/app/knowledge-view"
import { OrganizationView } from "@/components/app/organization-view"
import { OrganizationAccessDialog } from "@/components/organizations/organization-access-dialog"
import { PromptLibrary } from "@/components/app/prompt-library"
import { SettingsView } from "@/components/app/settings-view"
import { julesApi } from "@/lib/api"
import { demoAuditEvents, demoConversations, demoInvitations, demoKnowledgeBases, demoKnowledgeReview, demoMembers, demoMessages, demoModels, demoOrganizations, demoPrompts, demoSettings, demoUser } from "@/lib/demo-data"
import type { Artifact, ArtifactRequest, Attachment, Citation, Conversation, Effort, Invitation, KnowledgeBase, Message, Organization, OrganizationBrandKit, Prompt, PromptVersion, UserSettings, View } from "@/lib/types"

const FALLBACK_RESPONSE = "I’ve organized the request into a practical business answer.\n\n### Recommended approach\n\n1. **Clarify the decision.** State the outcome, owner, and time horizon.\n2. **Prioritize the evidence.** Lead with the facts that materially change the decision.\n3. **Make the next move explicit.** End with an accountable action and measurable checkpoint."

interface JulesAppProps {
  initialOrganizationId?: string
  initialOrganizations?: Organization[]
  onOrganizationChange?: (id: string) => void
  onMembershipsChange?: () => void
  onSignOut?: () => void
}

export function JulesApp(props: JulesAppProps = {}) {
  const [activeView, setActiveView] = useState<View>("chat")
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const [organizationDialogOpen, setOrganizationDialogOpen] = useState(false)
  const [organizations, setOrganizations] = useState(props.initialOrganizations ?? demoOrganizations)
  const [activeOrganizationId, setActiveOrganizationId] = useState(props.initialOrganizationId ?? demoUser.active_organization_id)
  const [user, setUser] = useState(demoUser)
  const [conversations, setConversations] = useState(demoConversations)
  const [activeConversationId, setActiveConversationId] = useState(demoConversations[0].id)
  const [messages, setMessages] = useState<Record<string, Message[]>>(demoMessages)
  const [prompts, setPrompts] = useState(demoPrompts)
  const [settings, setSettings] = useState(demoSettings)
  const [brandKit, setBrandKit] = useState<OrganizationBrandKit>({ primary_color: "#4C1D95", accent_color: "#7C3AED", heading_font: "Aptos Display", body_font: "Aptos", footer_text: "", has_logo: false, can_manage: false, available_fonts: ["Aptos", "Aptos Display", "Arial", "Calibri", "Georgia", "Times New Roman"] })
  const [models, setModels] = useState(demoModels)
  const [members, setMembers] = useState(demoMembers)
  const [invitations, setInvitations] = useState(demoInvitations)
  const [auditEvents, setAuditEvents] = useState(demoAuditEvents)
  const [knowledgeBases, setKnowledgeBases] = useState(demoKnowledgeBases)
  const [activeKnowledgeBaseId, setActiveKnowledgeBaseId] = useState(demoKnowledgeBases[0]?.id ?? "")
  const [activeKnowledgeBase, setActiveKnowledgeBase] = useState<KnowledgeBase | undefined>(demoKnowledgeBases[0])
  const [knowledgeReview, setKnowledgeReview] = useState(demoKnowledgeReview)
  const [draft, setDraft] = useState("")
  const [model, setModel] = useState(demoConversations[0].model)
  const [effort, setEffort] = useState<Effort>(demoConversations[0].effort)
  const [selectedKnowledgeBaseIds, setSelectedKnowledgeBaseIds] = useState(demoConversations[0].knowledge_base_ids)
  const [webSearchEnabled, setWebSearchEnabled] = useState(demoConversations[0].web_search_enabled)
  const [pendingFiles, setPendingFiles] = useState<Array<{ attachment: Attachment; file: File }>>([])
  const [streaming, setStreaming] = useState(false)
  const [artifactRequest, setArtifactRequest] = useState<ArtifactRequest | undefined>()
  const backendConnected = useRef(false)
  const streamController = useRef<AbortController | null>(null)
  const activeOrganizationRef = useRef(activeOrganizationId)

  useEffect(() => { activeOrganizationRef.current = activeOrganizationId }, [activeOrganizationId])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      julesApi.organizations(), julesApi.me(activeOrganizationId), julesApi.conversations(activeOrganizationId), julesApi.prompts(activeOrganizationId), julesApi.settings(activeOrganizationId), julesApi.models(activeOrganizationId), julesApi.members(activeOrganizationId), julesApi.invitations(activeOrganizationId).catch(() => []), julesApi.auditEvents(activeOrganizationId).catch(() => []), julesApi.knowledgeBases(activeOrganizationId), julesApi.knowledgeReview(activeOrganizationId).catch(() => demoKnowledgeReview), julesApi.brandKit(activeOrganizationId),
    ]).then(([nextOrganizations, profile, nextConversations, nextPrompts, nextSettings, modelPolicy, nextMembers, nextInvitations, nextAudit, nextKnowledgeBases, nextReview, nextBrandKit]) => {
      if (cancelled) return
      backendConnected.current = true
      setOrganizations(nextOrganizations); setUser(profile); setConversations(nextConversations); setPrompts(nextPrompts); setSettings(nextSettings); setModels(modelPolicy.models); setMembers(nextMembers); setInvitations(nextInvitations); setAuditEvents(nextAudit); setKnowledgeBases(nextKnowledgeBases); setKnowledgeReview(nextReview); setBrandKit(nextBrandKit)
      if (nextConversations.length) { setActiveConversationId(nextConversations[0].id); setSelectedKnowledgeBaseIds(nextConversations[0].knowledge_base_ids); setWebSearchEnabled(nextConversations[0].web_search_enabled) }
      else { setSelectedKnowledgeBaseIds(nextKnowledgeBases.map((item) => item.id)); setWebSearchEnabled(nextSettings.web_search_default) }
      if (nextKnowledgeBases.length) setActiveKnowledgeBaseId(nextKnowledgeBases[0].id)
    }).catch(() => {
      if (cancelled) return
      backendConnected.current = false
      if (activeOrganizationId !== "org-northstar") { setConversations([]); setMessages({}); setPrompts([]) }
    })
    return () => { cancelled = true }
  }, [activeOrganizationId])

  useEffect(() => {
    if (!backendConnected.current || !activeConversationId) return
    julesApi.conversation(activeOrganizationId, activeConversationId).then((conversation) => {
      setMessages((current) => ({ ...current, [activeConversationId]: conversation.messages }))
      setModel(conversation.model); setEffort(conversation.effort); setSelectedKnowledgeBaseIds(conversation.knowledge_base_ids); setWebSearchEnabled(conversation.web_search_enabled)
    }).catch(() => undefined)
  }, [activeConversationId, activeOrganizationId])

  useEffect(() => {
    if (!backendConnected.current || !activeKnowledgeBaseId) { setActiveKnowledgeBase(knowledgeBases.find((item) => item.id === activeKnowledgeBaseId)); return }
    julesApi.knowledgeBase(activeOrganizationId, activeKnowledgeBaseId).then(setActiveKnowledgeBase).catch(() => setActiveKnowledgeBase(undefined))
  }, [activeKnowledgeBaseId, activeOrganizationId, knowledgeBases])

  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? { id: "local-new", title: "New conversation", model, effort, pinned: false, archived: false, knowledge_base_ids: knowledgeBases.map((item) => item.id), web_search_enabled: settings.web_search_default, updated_at: new Date().toISOString() }
  const activeMessages = messages[activeConversation.id] ?? []
  // Selections can outlive their knowledge base: the initial demo state is replaced by the
  // backend fetch, and bases can be archived or deleted mid-session. Stale ids are invisible
  // in the picker but still counted in the label and rejected with a 403 on send.
  const activeKnowledgeBaseIds = useMemo(() => {
    const available = new Set(knowledgeBases.map((item) => item.id))
    return selectedKnowledgeBaseIds.filter((id) => available.has(id))
  }, [knowledgeBases, selectedKnowledgeBaseIds])
  const activeRole = organizations.find((organization) => organization.id === activeOrganizationId)?.role ?? user.role
  const canReviewKnowledge = activeRole === "owner" || activeRole === "admin"
  const visibleView: View = activeView === "review" && !canReviewKnowledge ? "chat" : activeView
  const activeUser = activeRole === user.role ? user : { ...user, role: activeRole }

  async function newChat() {
    let conversation: Conversation = { id: crypto.randomUUID(), title: "New conversation", model: settings.default_model, effort: settings.default_effort, pinned: false, archived: false, knowledge_base_ids: knowledgeBases.map((item) => item.id), web_search_enabled: settings.web_search_default, updated_at: new Date().toISOString() }
    if (backendConnected.current) {
      try { conversation = await julesApi.createConversation(activeOrganizationId, conversation) } catch { toast.error("Created locally; the API is unavailable.") }
    }
    setConversations((current) => [conversation, ...current]); setMessages((current) => ({ ...current, [conversation.id]: [] })); setActiveConversationId(conversation.id); setModel(conversation.model); setEffort(conversation.effort); setSelectedKnowledgeBaseIds(conversation.knowledge_base_ids); setWebSearchEnabled(conversation.web_search_enabled); setDraft(""); setActiveView("chat")
  }

  function selectConversation(id: string) {
    const conversation = conversations.find((item) => item.id === id)
    if (conversation) { setActiveConversationId(id); setModel(conversation.model); setEffort(conversation.effort); setSelectedKnowledgeBaseIds(conversation.knowledge_base_ids); setWebSearchEnabled(conversation.web_search_enabled); setActiveView("chat") }
  }

  async function conversationAction(id: string, action: "pin" | "archive" | "delete") {
    const conversation = conversations.find((item) => item.id === id); if (!conversation) return
    if (action === "delete") {
      const remaining = conversations.filter((item) => item.id !== id)
      setConversations(remaining); setMessages((current) => { const next = { ...current }; delete next[id]; return next })
      if (backendConnected.current) julesApi.deleteConversation(activeOrganizationId, id).catch(() => toast.error("The server could not delete this conversation."))
      if (id === activeConversationId) {
        streamController.current?.abort(); setStreaming(false); setPendingFiles([]); setDraft("")
        const nextConversation = remaining.find((item) => !item.archived)
        if (nextConversation) selectConversation(nextConversation.id)
        else {
          setActiveConversationId(""); setModel(settings.default_model); setEffort(settings.default_effort); setSelectedKnowledgeBaseIds(knowledgeBases.map((item) => item.id)); setWebSearchEnabled(settings.web_search_default)
        }
      }
      return
    }
    const changes = action === "pin" ? { pinned: !conversation.pinned } : { archived: true }
    setConversations((current) => current.map((item) => item.id === id ? { ...item, ...changes } : item))
    if (backendConnected.current) julesApi.updateConversation(activeOrganizationId, id, changes).catch(() => toast.error("The server could not save that change."))
  }

  async function addFile(file: File) {
    if (file.size > 50 * 1024 * 1024) { toast.error("Files must be 50 MB or smaller."); return }
    let attachment: Attachment = { id: crypto.randomUUID(), file_name: file.name, mime_type: file.type || "application/octet-stream", size_bytes: file.size, scan_status: "clean" }
    if (backendConnected.current && !activeConversation.id.startsWith("local")) {
      try { attachment = await julesApi.uploadAttachment(activeOrganizationId, activeConversation.id, file) } catch { toast.error("The upload is available locally only.") }
    }
    setPendingFiles((current) => [...current, { attachment, file }])
  }

  async function simulateResponse(conversationId: string, messageId: string) {
    const words = FALLBACK_RESPONSE.split(" ")
    for (const word of words) {
      await new Promise((resolve) => window.setTimeout(resolve, 22))
      setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === messageId ? { ...item, content: `${item.content}${word} ` } : item) }))
    }
  }

  function updateArtifactInMessages(nextArtifact: Artifact) {
    setMessages((current) => {
      const next = { ...current }
      for (const [conversationId, rows] of Object.entries(next)) {
        next[conversationId] = rows.map((message) => message.artifacts?.some((item) => item.id === nextArtifact.id)
          ? { ...message, artifacts: message.artifacts.map((item) => item.id === nextArtifact.id ? nextArtifact : item) }
          : message)
      }
      return next
    })
  }

  function removeArtifactFromMessages(artifactId: string) {
    setMessages((current) => Object.fromEntries(Object.entries(current).map(([conversationId, rows]) => [conversationId, rows.map((message) => ({ ...message, artifacts: message.artifacts?.filter((item) => item.id !== artifactId) }))])))
  }

  async function watchArtifact(organizationId: string, artifactId: string) {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000))
      if (activeOrganizationRef.current !== organizationId) return
      try {
        const next = await julesApi.artifact(organizationId, artifactId)
        updateArtifactInMessages(next)
        if (["ready", "failed", "cancelled"].includes(next.status)) {
          if (next.status === "ready") toast.success(`${next.format.toUpperCase()} file is ready`)
          if (next.status === "failed") toast.error(next.error || "File generation failed")
          return
        }
      } catch { return }
    }
  }

  async function sendMessage(override?: string) {
    const content = (override ?? draft).trim(); if (!content || streaming) return
    let conversation = activeConversation
    let attachments = pendingFiles.map((item) => item.attachment)
    if (backendConnected.current && conversation.id.startsWith("local")) {
      try {
        conversation = await julesApi.createConversation(activeOrganizationId, conversation)
        setConversations((current) => [conversation, ...current]); setActiveConversationId(conversation.id)
        if (pendingFiles.length) {
          try { attachments = await Promise.all(pendingFiles.map((item) => julesApi.uploadAttachment(activeOrganizationId, conversation.id, item.file))) }
          catch { toast.error("The attachments could not be uploaded. Your message was not sent."); return }
        }
      } catch { toast.error("The new conversation is available locally only.") }
    }
    const conversationId = conversation.id
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content, status: "completed", created_at: new Date().toISOString(), attachments, knowledge_base_ids: activeKnowledgeBaseIds, web_search_enabled: webSearchEnabled }
    const requestedArtifact = artifactRequest
    let assistantId = crypto.randomUUID()
    const activity = requestedArtifact
      ? `Thinking through your ${requestedArtifact.format === "pptx" ? "presentation" : "document"}`
      : activeKnowledgeBaseIds.length && webSearchEnabled
        ? "Thinking with company and web sources"
        : activeKnowledgeBaseIds.length
          ? "Thinking with company knowledge"
          : webSearchEnabled
            ? "Thinking and researching the web"
            : "Thinking"
    const assistantMessage: Message = { id: assistantId, role: "assistant", content: "", status: "streaming", created_at: new Date().toISOString(), knowledge_base_ids: activeKnowledgeBaseIds, web_search_enabled: webSearchEnabled, activity }
    setMessages((current) => ({ ...current, [conversationId]: [...(current[conversationId] ?? []), userMessage, assistantMessage] }))
    if (conversation.title === "New conversation") setConversations((current) => current.map((item) => item.id === conversationId ? { ...item, title: content.split("\n")[0].slice(0, 60) } : item))
    setDraft(""); setPendingFiles([]); setArtifactRequest(undefined); setStreaming(true)
    const controller = new AbortController(); streamController.current = controller
    try {
      if (!backendConnected.current || conversationId.startsWith("local")) await simulateResponse(conversationId, assistantId)
      else await julesApi.streamMessage(activeOrganizationId, conversationId, { content, model, effort, attachment_ids: attachments.map((item) => item.id), knowledge_base_ids: activeKnowledgeBaseIds, web_search_enabled: webSearchEnabled, artifact_request: requestedArtifact }, ({ event, data }) => {
        if (event === "message_started" && typeof data.message_id === "string") {
          const previousId = assistantId; assistantId = data.message_id
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === previousId ? { ...item, id: assistantId } : item) }))
        } else if (event === "retrieval_started") {
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, activity: item.knowledge_base_ids?.length ? "Thinking through company knowledge" : item.web_search_enabled ? "Thinking and researching the web" : "Thinking" } : item) }))
        } else if (event === "text_delta" && typeof data.text === "string") {
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, content: item.content + data.text } : item) }))
        } else if (event === "clarification_required" && typeof data.question === "string") {
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, content: data.question as string, grounding_status: "clarification_required" } : item) }))
        } else if ((event === "internal_citations" || event === "web_citations") && Array.isArray(data.citations)) {
          const citations = data.citations as Citation[]
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, citations: [...(item.citations?.filter((citation) => citation.source_type !== citations[0]?.source_type) ?? []), ...citations] } : item) }))
        } else if (event === "grounding_status" && typeof data.status === "string") {
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, grounding_status: data.status as string } : item) }))
        } else if (event === "artifact_queued" && data.artifact && typeof data.artifact === "object") {
          const artifact = data.artifact as unknown as Artifact
          setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, artifacts: [...(item.artifacts ?? []), artifact] } : item) }))
          void watchArtifact(activeOrganizationId, artifact.id)
        }
      }, controller.signal)
      setConversations((current) => current.map((item) => item.id === conversationId ? { ...item, knowledge_base_ids: activeKnowledgeBaseIds, web_search_enabled: webSearchEnabled } : item))
      setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, status: "completed" } : item) }))
    } catch (error) {
      if ((error as Error).name !== "AbortError") { setMessages((current) => ({ ...current, [conversationId]: (current[conversationId] ?? []).map((item) => item.id === assistantId ? { ...item, status: "error", content: item.content || "Jules AI could not complete that response. Please try again." } : item) })); toast.error("The response was interrupted.") }
    } finally { setStreaming(false); streamController.current = null }
  }

  function stopStreaming() { streamController.current?.abort(); setStreaming(false); setMessages((current) => ({ ...current, [activeConversation.id]: (current[activeConversation.id] ?? []).map((item) => item.status === "streaming" ? { ...item, status: "completed", content: item.content || "Response stopped." } : item) })) }
  function regenerate() { const lastUser = [...activeMessages].reverse().find((message) => message.role === "user"); if (lastUser) void sendMessage(lastUser.content) }

  async function toggleFavorite(id: string) {
    setPrompts((current) => current.map((prompt) => prompt.id === id ? { ...prompt, favorite: !prompt.favorite } : prompt))
    if (backendConnected.current) julesApi.toggleFavorite(activeOrganizationId, id).catch(() => toast.error("Favorite was saved locally only."))
  }

  async function savePrompt(value: Pick<Prompt, "title" | "description" | "body" | "tags">, id?: string) {
    if (id) {
      setPrompts((current) => current.map((prompt) => prompt.id === id ? { ...prompt, ...value, version_number: prompt.version_number + 1, updated_at: new Date().toISOString(), last_editor: user.display_name } : prompt))
      if (backendConnected.current) julesApi.updatePrompt(activeOrganizationId, id, value).catch(() => toast.error("Prompt was saved locally only."))
    } else {
      let prompt: Prompt = { id: crypto.randomUUID(), ...value, favorite: false, archived: false, version_number: 1, updated_at: new Date().toISOString(), last_editor: user.display_name }
      if (backendConnected.current) { try { prompt = await julesApi.createPrompt(activeOrganizationId, value) } catch { toast.error("Prompt was created locally only.") } }
      setPrompts((current) => [prompt, ...current])
    }
    toast.success("Organization prompt saved")
  }

  async function loadPromptVersions(prompt: Prompt): Promise<PromptVersion[]> {
    if (backendConnected.current) {
      try { return await julesApi.promptVersions(activeOrganizationId, prompt.id) }
      catch { toast.error("Version history is temporarily unavailable.") }
    }
    return [{ id: `${prompt.id}-${prompt.version_number}`, version_number: prompt.version_number, title: prompt.title, body: prompt.body, created_at: prompt.updated_at }]
  }

  async function restorePromptVersion(prompt: Prompt, version: number) {
    if (!backendConnected.current) return
    try {
      const restored = await julesApi.restorePrompt(activeOrganizationId, prompt.id, version)
      setPrompts((current) => current.map((item) => item.id === prompt.id ? restored : item))
      toast.success(`Version ${version} restored as a new version`)
    } catch { toast.error("The prompt version could not be restored.") }
  }

  async function saveSettings(next: UserSettings) {
    setSettings(next)
    if (backendConnected.current) julesApi.updateSettings(activeOrganizationId, next).catch(() => toast.error("Preferences were saved locally only."))
    toast.success("Preferences saved")
  }

  async function saveBrandKit(next: OrganizationBrandKit) {
    try {
      const updated = await julesApi.updateBrandKit(activeOrganizationId, next)
      setBrandKit(updated)
      toast.success("Organization brand kit saved")
    } catch (error) { toast.error(error instanceof Error ? error.message : "Brand kit could not be saved.") }
  }

  async function uploadBrandLogo(file: File) {
    try {
      const updated = await julesApi.uploadBrandLogo(activeOrganizationId, file)
      setBrandKit(updated)
      toast.success("Brand logo uploaded")
    } catch (error) { toast.error(error instanceof Error ? error.message : "Brand logo could not be uploaded.") }
  }

  function artifactUpdated(artifact: Artifact) {
    updateArtifactInMessages(artifact)
    if (!["ready", "failed", "cancelled"].includes(artifact.status)) void watchArtifact(activeOrganizationId, artifact.id)
  }

  function changeKnowledgeScope(ids: string[]) {
    setSelectedKnowledgeBaseIds(ids)
    setConversations((current) => current.map((item) => item.id === activeConversation.id ? { ...item, knowledge_base_ids: ids } : item))
    if (backendConnected.current && !activeConversation.id.startsWith("local")) julesApi.updateConversation(activeOrganizationId, activeConversation.id, { knowledge_base_ids: ids }).catch(() => toast.error("Knowledge selection was saved locally only."))
  }

  function changeWebSearch(enabled: boolean) {
    setWebSearchEnabled(enabled)
    setConversations((current) => current.map((item) => item.id === activeConversation.id ? { ...item, web_search_enabled: enabled } : item))
    if (backendConnected.current && !activeConversation.id.startsWith("local")) julesApi.updateConversation(activeOrganizationId, activeConversation.id, { web_search_enabled: enabled }).catch(() => toast.error("Web-search choice was saved locally only."))
  }

  async function createKnowledgeBase(title: string, description: string) {
    try {
      const row = backendConnected.current ? await julesApi.createKnowledgeBase(activeOrganizationId, { title, description }) : { id: crypto.randomUUID(), title, description, archived: false, document_count: 0, member_count: 1, can_manage: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }
      setKnowledgeBases((current) => [...current, row]); setActiveKnowledgeBaseId(row.id); toast.success("Knowledge base created")
    } catch (error) { toast.error(error instanceof Error ? error.message : "Knowledge base could not be created.") }
  }

  async function uploadKnowledge(knowledgeBaseId: string, files: File[]) {
    try {
      if (!backendConnected.current) throw new Error("Connect the API before uploading knowledge documents.")
      await julesApi.uploadKnowledgeDocuments(activeOrganizationId, knowledgeBaseId, files)
      const detail = await julesApi.knowledgeBase(activeOrganizationId, knowledgeBaseId)
      setActiveKnowledgeBase(detail); setKnowledgeBases((current) => current.map((item) => item.id === knowledgeBaseId ? { ...item, document_count: detail.document_count, updated_at: detail.updated_at } : item)); toast.success(`${files.length} document${files.length === 1 ? "" : "s"} queued for ingestion`)
    } catch (error) { toast.error(error instanceof Error ? error.message : "Documents could not be uploaded.") }
  }

  async function updateKnowledgeBaseDetails(knowledgeBaseId: string, title: string, description: string) {
    const current = knowledgeBases.find((item) => item.id === knowledgeBaseId)
    if (!current) return
    try {
      const updated = backendConnected.current
        ? await julesApi.updateKnowledgeBase(activeOrganizationId, knowledgeBaseId, { title, description })
        : { ...current, title, description, updated_at: new Date().toISOString() }
      setKnowledgeBases((items) => items.map((item) => item.id === knowledgeBaseId ? { ...item, ...updated } : item))
      setActiveKnowledgeBase((item) => item?.id === knowledgeBaseId ? { ...item, ...updated } : item)
      toast.success("Knowledge base settings saved")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Knowledge base settings could not be saved.")
    }
  }

  async function updateKnowledgeAccess(knowledgeBaseId: string, userIds: string[], reason: string) {
    try { await julesApi.updateKnowledgeAccess(activeOrganizationId, knowledgeBaseId, userIds, reason); setActiveKnowledgeBase(await julesApi.knowledgeBase(activeOrganizationId, knowledgeBaseId)); toast.success("Knowledge access updated") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Access could not be updated.") }
  }

  async function archiveKnowledgeBase(knowledgeBaseId: string) {
    try { if (backendConnected.current) await julesApi.updateKnowledgeBase(activeOrganizationId, knowledgeBaseId, { archived: true }); setKnowledgeBases((current) => current.filter((item) => item.id !== knowledgeBaseId)); setActiveKnowledgeBaseId(""); setActiveKnowledgeBase(undefined); toast.success("Knowledge base archived") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Knowledge base could not be archived.") }
  }

  async function resolveConflict(id: string, action: string) {
    try { await julesApi.resolveConflict(activeOrganizationId, id, action); setKnowledgeReview(await julesApi.knowledgeReview(activeOrganizationId)); toast.success("Conflict resolved") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Conflict could not be resolved.") }
  }

  async function reviewProposal(id: string, decision: "approved" | "rejected") {
    try { await julesApi.reviewProposal(activeOrganizationId, id, decision); setKnowledgeReview(await julesApi.knowledgeReview(activeOrganizationId)); toast.success(`Proposal ${decision}`) }
    catch (error) { toast.error(error instanceof Error ? error.message : "Proposal could not be reviewed.") }
  }

  async function saveMessageToKnowledge(message: Message, knowledgeBaseId: string, title: string) {
    try { await julesApi.createKnowledgeProposal(activeOrganizationId, { knowledge_base_id: knowledgeBaseId, conversation_id: activeConversation.id, message_id: message.id, title, content: message.content }); toast.success("Submitted to Knowledge Review") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Knowledge proposal could not be submitted.") }
  }

  async function reportAnswer(message: Message) {
    const note = window.prompt("What is incorrect or outdated about this answer?", "")
    if (note === null) return
    try { await julesApi.feedback(activeOrganizationId, message.id, "incorrect", note); toast.success("Answer sent to Knowledge Review") }
    catch (error) { toast.error(error instanceof Error ? error.message : "Feedback could not be recorded.") }
  }

  async function invite(email: string): Promise<string | undefined> {
    let invitation: Invitation = { id: crypto.randomUUID(), email, role: "member", status: "pending", expires_at: new Date(Date.now() + 7 * 864e5).toISOString() }
    if (backendConnected.current) { try { invitation = await julesApi.invite(activeOrganizationId, email) } catch { toast.error("Invitation was added locally only.") } }
    setInvitations((current) => current.some((item) => item.id === invitation.id) ? current.map((item) => item.id === invitation.id ? invitation : item) : [invitation, ...current])
    toast.success(`Invitation created for ${email}`)
    return invitation.acceptance_token ? `${window.location.origin}/invite/${invitation.acceptance_token}` : undefined
  }

  async function saveModelPolicy(defaultModel: string, maximumEffort: Effort) {
    if (backendConnected.current) {
      try { await julesApi.updateModelPolicy(activeOrganizationId, { allowed_models: models.map((item) => item.id), default_model: defaultModel, maximum_effort: maximumEffort }) }
      catch { toast.error("The model policy was saved locally only."); return }
    }
    toast.success("Model policy saved")
  }

  async function resendInvitation(id: string): Promise<string | undefined> {
    if (backendConnected.current) {
      try {
        const next = await julesApi.resendInvitation(activeOrganizationId, id)
        setInvitations((current) => current.map((item) => item.id === id ? next : item))
        toast.success("Invitation link rotated")
        return next.acceptance_token ? `${window.location.origin}/invite/${next.acceptance_token}` : undefined
      } catch { toast.error("Invitation could not be resent."); return undefined }
    }
    toast.success("Invitation resent")
    return undefined
  }

  async function revokeInvitation(id: string) {
    if (backendConnected.current) {
      try { await julesApi.revokeInvitation(activeOrganizationId, id) }
      catch { toast.error("Invitation could not be revoked."); return }
    }
    setInvitations((current) => current.map((item) => item.id === id ? { ...item, status: "revoked" } : item))
    toast.success("Invitation revoked")
  }

  async function deleteAllConversations() {
    setConversations([]); setMessages({}); setActiveConversationId("")
    if (backendConnected.current) julesApi.deleteAllConversations(activeOrganizationId).catch(() => toast.error("The server could not complete deletion."))
    toast.success("Your conversations were deleted")
  }

  async function deleteAccount() {
    if (!backendConnected.current) { toast.error("Connect the API before deleting an account."); return }
    try { await julesApi.deleteAccount(); toast.success("Your personal account was deleted") }
    catch (error) { toast.error(error instanceof Error ? error.message : "The account could not be deleted.") }
  }

  function switchOrganization(id: string) {
    if (id === activeOrganizationId) return
    streamController.current?.abort()
    setConversations([]); setMessages({}); setPrompts([]); setMembers([]); setInvitations([]); setAuditEvents([]); setKnowledgeBases([]); setActiveKnowledgeBase(undefined); setActiveKnowledgeBaseId(""); setActiveConversationId(""); setPendingFiles([]); setKnowledgeReview(demoKnowledgeReview); setArtifactRequest(undefined)
    setActiveOrganizationId(id); setActiveView("chat"); setMobileNavigationOpen(false)
    props.onOrganizationChange?.(id)
  }

  function organizationReady(organization: Organization) {
    setOrganizations((current) => current.some((item) => item.id === organization.id) ? current : [...current, organization])
    props.onMembershipsChange?.()
    if (organization.id !== activeOrganizationId) switchOrganization(organization.id)
  }

  async function leaveOrganization(id: string) {
    try {
      await julesApi.leaveOrganization(id)
      const remaining = organizations.filter((item) => item.id !== id)
      setOrganizations(remaining)
      props.onMembershipsChange?.()
      if (id === activeOrganizationId && remaining.length) switchOrganization(remaining[0].id)
      toast.success("You left the organization")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "The organization could not be left.")
    }
  }

  const sidebar = <AppSidebar user={activeUser} organizations={organizations} activeOrganizationId={activeOrganizationId} conversations={conversations} activeConversationId={activeConversationId} activeView={visibleView} onOrganizationChange={switchOrganization} onManageOrganizations={() => setOrganizationDialogOpen(true)} onSignOut={() => props.onSignOut?.()} onNewChat={() => void newChat()} onSelectConversation={selectConversation} onViewChange={setActiveView} onConversationAction={(id, action) => void conversationAction(id, action)} onNavigate={() => setMobileNavigationOpen(false)} />

  return <main className="flex h-dvh min-h-0 w-full overflow-hidden bg-background">
    <div className="hidden h-full w-[272px] shrink-0 border-r lg:block">{sidebar}</div>
    <Sheet open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen}><SheetContent side="left" className="w-[min(86vw,340px)] p-0" showCloseButton={false}><SheetHeader className="sr-only"><SheetTitle>Jules AI navigation</SheetTitle><SheetDescription>Choose an organization, conversation, or settings page.</SheetDescription></SheetHeader>{sidebar}</SheetContent></Sheet>
    {visibleView === "chat" ? <ChatView organizationId={activeOrganizationId} conversation={activeConversation} messages={activeMessages} models={models} knowledgeBases={knowledgeBases} selectedKnowledgeBaseIds={activeKnowledgeBaseIds} webSearchEnabled={webSearchEnabled} artifactRequest={artifactRequest} draft={draft} effort={effort} model={model} pendingAttachments={pendingFiles.map((item) => item.attachment)} streaming={streaming} onDraftChange={setDraft} onEffortChange={setEffort} onModelChange={setModel} onKnowledgeBaseIdsChange={changeKnowledgeScope} onWebSearchChange={changeWebSearch} onArtifactRequestChange={setArtifactRequest} onArtifactUpdated={artifactUpdated} onArtifactDeleted={removeArtifactFromMessages} onSend={() => void sendMessage()} onStop={stopStreaming} onOpenPrompts={() => setActiveView("prompts")} onFileSelect={(file) => void addFile(file)} onRemoveAttachment={(id) => setPendingFiles((current) => current.filter((item) => item.attachment.id !== id))} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} onRegenerate={regenerate} onSaveKnowledge={(message, knowledgeBaseId, title) => void saveMessageToKnowledge(message, knowledgeBaseId, title)} onReportAnswer={(message) => void reportAnswer(message)} /> : null}
    {visibleView === "knowledge" ? <KnowledgeView knowledgeBases={knowledgeBases} activeKnowledgeBase={activeKnowledgeBase} members={members} role={activeRole} onSelect={setActiveKnowledgeBaseId} onCreate={(title, description) => void createKnowledgeBase(title, description)} onUpdate={(knowledgeBaseId, title, description) => void updateKnowledgeBaseDetails(knowledgeBaseId, title, description)} onUpload={(knowledgeBaseId, files) => void uploadKnowledge(knowledgeBaseId, files)} onUpdateAccess={(knowledgeBaseId, userIds, reason) => void updateKnowledgeAccess(knowledgeBaseId, userIds, reason)} onArchive={(knowledgeBaseId) => void archiveKnowledgeBase(knowledgeBaseId)} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} /> : null}
    {visibleView === "review" && canReviewKnowledge ? <KnowledgeReviewView review={knowledgeReview} onResolveConflict={(id, action) => void resolveConflict(id, action)} onReviewProposal={(id, decision) => void reviewProposal(id, decision)} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} /> : null}
    {visibleView === "prompts" ? <PromptLibrary prompts={prompts} role={activeRole} onUsePrompt={(body) => { if (draft.trim() && !window.confirm("Replace the text already in the composer?")) return; setDraft(body); setActiveView("chat") }} onFavorite={(id) => void toggleFavorite(id)} onSave={(value, id) => void savePrompt(value, id)} onLoadVersions={loadPromptVersions} onRestoreVersion={restorePromptVersion} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} /> : null}
    {visibleView === "settings" ? <SettingsView key={`${activeOrganizationId}-${settings.theme}-${settings.default_model}-${settings.default_effort}-${settings.custom_instructions}-${settings.web_search_default}-${brandKit.updated_at}`} settings={settings} brandKit={brandKit} models={models} organizations={organizations} activeOrganizationId={activeOrganizationId} onOrganizationChange={switchOrganization} onManageOrganizations={() => setOrganizationDialogOpen(true)} onLeaveOrganization={(id) => void leaveOrganization(id)} onSave={(next) => void saveSettings(next)} onSaveBrandKit={(next) => void saveBrandKit(next)} onUploadBrandLogo={(file) => void uploadBrandLogo(file)} onDeleteAllConversations={() => void deleteAllConversations()} onDeleteAccount={() => void deleteAccount()} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} /> : null}
    {visibleView === "organization" ? <OrganizationView organizationName={organizations.find((item) => item.id === activeOrganizationId)?.name ?? "Organization"} members={members} invitations={invitations} auditEvents={auditEvents} models={models} onInvite={invite} onSavePolicy={(defaultModel, maximumEffort) => void saveModelPolicy(defaultModel, maximumEffort)} onResendInvitation={resendInvitation} onRevokeInvitation={(id) => void revokeInvitation(id)} onOpenMobileNavigation={() => setMobileNavigationOpen(true)} /> : null}
    <OrganizationAccessDialog open={organizationDialogOpen} onOpenChange={setOrganizationDialogOpen} onOrganizationReady={organizationReady} />
  </main>
}
