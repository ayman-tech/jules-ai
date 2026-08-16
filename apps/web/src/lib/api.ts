import type { Artifact, ArtifactRequest, AuditEvent, AuthBootstrap, Conversation, Invitation, InvitationPreview, KnowledgeBase, KnowledgeReview, Member, Message, ModelOption, Organization, OrganizationDocumentTemplate, Prompt, PromptVersion, ResearchMode, StreamEvent, UserProfile, UserSettings } from "@/lib/types"

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1"
export const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "development"
let authTokenProvider: (() => Promise<string | null>) | null = null

export function setAuthTokenProvider(provider: (() => Promise<string | null>) | null) {
  authTokenProvider = provider
}

async function headers(organizationId?: string, json = true): Promise<HeadersInit> {
  const result: Record<string, string> = {}
  if (json) result["Content-Type"] = "application/json"
  if (AUTH_MODE === "development") result["X-User-ID"] = "user-ayman"
  else {
    const token = await authTokenProvider?.()
    if (token) result.Authorization = `Bearer ${token}`
  }
  if (organizationId) result["X-Organization-ID"] = organizationId
  return result
}

async function request<T>(path: string, organizationId?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { ...await headers(organizationId), ...init?.headers } })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }))
    const detail = Array.isArray(error.detail) ? error.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(", ") : error.detail
    if (response.status === 403 && detail === "No active organization membership" && typeof window !== "undefined") {
      window.dispatchEvent(new Event("jules:membership-invalid"))
    }
    throw new Error(detail ?? "Request failed")
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

export const julesApi = {
  bootstrap: (displayName?: string) => request<AuthBootstrap>("/auth/bootstrap", undefined, { method: "POST", body: JSON.stringify(displayName ? { display_name: displayName } : {}) }),
  me: (organizationId?: string) => request<UserProfile>("/me", organizationId),
  organizations: () => request<Organization[]>("/organizations"),
  createOrganization: (name: string) => request<Organization>("/organizations", undefined, { method: "POST", body: JSON.stringify({ name }) }),
  leaveOrganization: (organizationId: string) => request<void>("/organizations/current/membership", organizationId, { method: "DELETE" }),
  invitationPreview: (token: string) => request<InvitationPreview>(`/invitations/${encodeURIComponent(token)}/preview`),
  acceptInvitation: (token: string) => request<{ organization_id: string; status: string; organization: Organization }>(`/invitations/${encodeURIComponent(token)}/accept`, undefined, { method: "POST" }),
  conversations: (organizationId: string) => request<Conversation[]>("/conversations", organizationId),
  conversation: (organizationId: string, id: string) => request<Conversation & { messages: Message[] }>(`/conversations/${id}`, organizationId),
  createConversation: (organizationId: string, body: Partial<Conversation>) => request<Conversation>("/conversations", organizationId, { method: "POST", body: JSON.stringify(body) }),
  updateConversation: (organizationId: string, id: string, body: Partial<Conversation>) => request<Conversation>(`/conversations/${id}`, organizationId, { method: "PATCH", body: JSON.stringify(body) }),
  deleteConversation: (organizationId: string, id: string) => request<void>(`/conversations/${id}`, organizationId, { method: "DELETE" }),
  prompts: (organizationId: string) => request<Prompt[]>("/prompts", organizationId),
  createPrompt: (organizationId: string, body: Pick<Prompt, "title" | "description" | "body" | "tags">) => request<Prompt>("/prompts", organizationId, { method: "POST", body: JSON.stringify(body) }),
  updatePrompt: (organizationId: string, id: string, body: Partial<Prompt>) => request<Prompt>(`/prompts/${id}`, organizationId, { method: "PATCH", body: JSON.stringify(body) }),
  toggleFavorite: (organizationId: string, id: string) => request<{ favorite: boolean }>(`/prompts/${id}/favorite`, organizationId, { method: "POST" }),
  promptVersions: (organizationId: string, id: string) => request<PromptVersion[]>(`/prompts/${id}/versions`, organizationId),
  restorePrompt: (organizationId: string, id: string, version: number) => request<Prompt>(`/prompts/${id}/versions/${version}/restore`, organizationId, { method: "POST" }),
  settings: (organizationId: string) => request<UserSettings>("/settings", organizationId),
  updateSettings: (organizationId: string, body: Partial<UserSettings>) => request<UserSettings>("/settings", organizationId, { method: "PATCH", body: JSON.stringify(body) }),
  documentTemplate: (organizationId: string) => request<OrganizationDocumentTemplate>("/organizations/current/document-template", organizationId),
  async uploadDocumentTemplate(organizationId: string, file: File) {
    const form = new FormData(); form.append("upload", file)
    const response = await fetch(`${API_URL}/organizations/current/document-template`, { method: "POST", headers: await headers(organizationId, false), body: form })
    if (!response.ok) { const error = await response.json().catch(() => ({ detail: "Template upload failed" })); throw new Error(error.detail ?? "Template upload failed") }
    return response.json() as Promise<OrganizationDocumentTemplate>
  },
  activateDocumentTemplate: (organizationId: string, versionId: string) => request<OrganizationDocumentTemplate>(`/organizations/current/document-template/versions/${versionId}/activate`, organizationId, { method: "POST" }),
  disableDocumentTemplate: (organizationId: string) => request<OrganizationDocumentTemplate>("/organizations/current/document-template/disable", organizationId, { method: "POST" }),
  async documentTemplateBlob(organizationId: string, versionId: string) {
    const response = await fetch(`${API_URL}/organizations/current/document-template/versions/${versionId}/download`, { headers: await headers(organizationId, false) })
    if (!response.ok) throw new Error("Document template download failed")
    return response.blob()
  },
  async documentTemplatePreviewBlob(organizationId: string, versionId: string, previewNumber: number) {
    const response = await fetch(`${API_URL}/organizations/current/document-template/versions/${versionId}/previews/${previewNumber}`, { headers: await headers(organizationId, false) })
    if (!response.ok) throw new Error("Document template preview is unavailable")
    return response.blob()
  },
  members: (organizationId: string) => request<Member[]>("/organizations/current/members", organizationId),
  invitations: (organizationId: string) => request<Invitation[]>("/organizations/current/invitations", organizationId),
  invite: (organizationId: string, email: string) => request<Invitation>("/organizations/current/invitations", organizationId, { method: "POST", body: JSON.stringify({ email }) }),
  resendInvitation: (organizationId: string, id: string) => request<Invitation>(`/organizations/current/invitations/${id}/resend`, organizationId, { method: "POST" }),
  revokeInvitation: (organizationId: string, id: string) => request<void>(`/organizations/current/invitations/${id}`, organizationId, { method: "DELETE" }),
  models: (organizationId: string) => request<{ models: ModelOption[]; default_model: string; maximum_effort: string }>("/models", organizationId),
  updateModelPolicy: (organizationId: string, body: { allowed_models: string[]; default_model: string; maximum_effort: string }) => request<void>("/organizations/current/model-policy", organizationId, { method: "PATCH", body: JSON.stringify(body) }),
  auditEvents: (organizationId: string) => request<AuditEvent[]>("/audit-events", organizationId),
  knowledgeBases: (organizationId: string) => request<KnowledgeBase[]>("/knowledge-bases", organizationId),
  knowledgeBase: (organizationId: string, id: string) => request<KnowledgeBase>(`/knowledge-bases/${id}`, organizationId),
  createKnowledgeBase: (organizationId: string, body: { title: string; description: string; member_ids?: string[] }) => request<KnowledgeBase>("/knowledge-bases", organizationId, { method: "POST", body: JSON.stringify(body) }),
  updateKnowledgeBase: (organizationId: string, id: string, body: Partial<KnowledgeBase>) => request<KnowledgeBase>(`/knowledge-bases/${id}`, organizationId, { method: "PATCH", body: JSON.stringify(body) }),
  updateKnowledgeAccess: (organizationId: string, id: string, userIds: string[], reason: string) => request<void>(`/knowledge-bases/${id}/access`, organizationId, { method: "PUT", body: JSON.stringify({ user_ids: userIds, reason }) }),
  knowledgeReview: (organizationId: string) => request<KnowledgeReview>("/knowledge-review", organizationId),
  sourcePreview: (organizationId: string, chunkId: string) => request<{ chunk_id: string; title: string; content: string; page_number?: number | null; version?: number | null; kind: string }>(`/knowledge/sources/${chunkId}`, organizationId),
  async knowledgeVersionBlob(organizationId: string, documentId: string, versionId: string) {
    const response = await fetch(`${API_URL}/knowledge/documents/${documentId}/versions/${versionId}/content`, { headers: await headers(organizationId, false) })
    if (!response.ok) throw new Error("Source document is unavailable")
    return response.blob()
  },
  resolveConflict: (organizationId: string, id: string, action: string, note = "") => request<void>(`/knowledge-conflicts/${id}/resolve`, organizationId, { method: "POST", body: JSON.stringify({ action, note }) }),
  reviewProposal: (organizationId: string, id: string, decision: "approved" | "rejected", note = "") => request<void>(`/knowledge-proposals/${id}/review`, organizationId, { method: "POST", body: JSON.stringify({ decision, note }) }),
  createKnowledgeProposal: (organizationId: string, body: { knowledge_base_id: string; conversation_id?: string; message_id?: string; title: string; content: string }) => request<{ id: string; status: string }>("/knowledge-proposals", organizationId, { method: "POST", body: JSON.stringify(body) }),
  feedback: (organizationId: string, messageId: string, rating: "helpful" | "incorrect" | "outdated", note = "") => request<void>(`/messages/${messageId}/feedback`, organizationId, { method: "POST", body: JSON.stringify({ rating, note }) }),
  artifact: (organizationId: string, artifactId: string) => request<Artifact>(`/artifacts/${artifactId}`, organizationId),
  reviseArtifact: (organizationId: string, artifactId: string, instructions: string, useCurrentDocumentTemplate = false) => request<Artifact>(`/artifacts/${artifactId}/revisions`, organizationId, { method: "POST", body: JSON.stringify({ instructions, use_current_document_template: useCurrentDocumentTemplate }) }),
  retryArtifact: (organizationId: string, artifactId: string) => request<Artifact>(`/artifacts/${artifactId}/retry`, organizationId, { method: "POST" }),
  cancelArtifact: (organizationId: string, artifactId: string) => request<Artifact>(`/artifacts/${artifactId}/cancel`, organizationId, { method: "POST" }),
  deleteArtifact: (organizationId: string, artifactId: string) => request<void>(`/artifacts/${artifactId}`, organizationId, { method: "DELETE" }),
  saveArtifactToKnowledge: (organizationId: string, artifactId: string, knowledgeBaseId: string, title?: string) => request<void>(`/artifacts/${artifactId}/save-to-knowledge`, organizationId, { method: "POST", body: JSON.stringify({ knowledge_base_id: knowledgeBaseId, title }) }),
  async artifactBlob(organizationId: string, artifactId: string, version?: number) {
    const query = version ? `?version=${version}` : ""
    const response = await fetch(`${API_URL}/artifacts/${artifactId}/download${query}`, { headers: await headers(organizationId, false) })
    if (!response.ok) { const error = await response.json().catch(() => ({ detail: "Download failed" })); throw new Error(error.detail ?? "Download failed") }
    return response.blob()
  },
  async artifactPreviewBlob(organizationId: string, artifactId: string, previewNumber: number, version?: number) {
    const query = version ? `?version=${version}` : ""
    const response = await fetch(`${API_URL}/artifacts/${artifactId}/previews/${previewNumber}${query}`, { headers: await headers(organizationId, false) })
    if (!response.ok) throw new Error("Preview unavailable")
    return response.blob()
  },
  deleteAllConversations: (organizationId: string) => request<void>("/conversations", organizationId, { method: "DELETE" }),
  deleteAccount: () => request<void>("/me", undefined, { method: "DELETE" }),
  async uploadAttachment(organizationId: string, conversationId: string, file: File) {
    const form = new FormData(); form.append("upload", file)
    const response = await fetch(`${API_URL}/conversations/${conversationId}/attachments`, { method: "POST", headers: await headers(organizationId, false), body: form })
    if (!response.ok) throw new Error("Upload failed")
    return response.json()
  },
  async uploadKnowledgeDocuments(organizationId: string, knowledgeBaseId: string, files: File[]) {
    const form = new FormData(); files.forEach((file) => form.append("uploads", file))
    const response = await fetch(`${API_URL}/knowledge-bases/${knowledgeBaseId}/documents`, { method: "POST", headers: await headers(organizationId, false), body: form })
    if (!response.ok) { const error = await response.json().catch(() => ({ detail: "Upload failed" })); throw new Error(error.detail ?? "Upload failed") }
    return response.json()
  },
  async streamMessage(organizationId: string, conversationId: string, body: { content: string; model: string; effort: string; attachment_ids: string[]; knowledge_base_ids: string[]; web_search_enabled: boolean; research_mode?: ResearchMode; artifact_request?: ArtifactRequest }, onEvent: (event: StreamEvent) => void, signal: AbortSignal) {
    const response = await fetch(`${API_URL}/conversations/${conversationId}/messages/stream`, { method: "POST", headers: await headers(organizationId), body: JSON.stringify(body), signal })
    if (!response.ok || !response.body) throw new Error("Unable to stream response")
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      buffer += decoder.decode(value, { stream: true }); const events = buffer.split("\n\n"); buffer = events.pop() ?? ""
      for (const event of events) {
        const eventName = event.match(/^event: (.+)$/m)?.[1]; const data = event.match(/^data: (.+)$/m)?.[1]
        if (!data) continue
        const payload = JSON.parse(data)
        if (eventName) onEvent({ event: eventName, data: payload })
        if (eventName === "error") throw new Error(payload.message)
      }
    }
  },
}

export function extractPromptVariables(body: string): string[] {
  return Array.from(new Set(Array.from(body.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g), (match) => match[1])))
}
export function fillPromptVariables(body: string, values: Record<string, string>): string {
  return body.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key: string) => values[key] || `{{${key}}}`)
}
