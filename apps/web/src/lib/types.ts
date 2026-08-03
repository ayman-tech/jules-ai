export type View = "chat" | "knowledge" | "review" | "prompts" | "settings" | "organization"
export type Role = "owner" | "admin" | "member"
export type Effort = "low" | "medium" | "high"
export interface Organization { id: string; name: string; slug: string; role: Role }
export type OrganizationMembership = Organization
export interface AuthUser { id: string; display_name: string; email: string; avatar_url?: string | null }
export interface AuthState {
  user: AuthUser | null
  email_verified: boolean
  organizations: OrganizationMembership[]
  requires_onboarding: boolean
}
export type AuthBootstrap = Omit<AuthState, "user"> & { user: AuthUser }
export interface InvitationPreview {
  organization: Pick<Organization, "id" | "name" | "slug">
  invited_email: string
  role: Role
  status: "pending" | "accepted" | "expired" | "revoked"
  expires_at: string
}
export interface UserProfile { id: string; display_name: string; email: string; role: Role; active_organization_id: string }
export interface Conversation { id: string; title: string; model: string; effort: Effort; pinned: boolean; archived: boolean; knowledge_base_ids: string[]; web_search_enabled: boolean; updated_at: string }
export interface Attachment { id: string; file_name: string; mime_type: string; size_bytes: number; scan_status: string }
export interface Citation { id?: string; ordinal?: number; source_type: "company" | "web"; knowledge_base_id?: string | null; knowledge_base_title?: string; document_id?: string | null; version_id?: string | null; chunk_id?: string | null; title: string; location?: string | null; url?: string | null; publisher?: string | null; retrieved_at?: string | null; metadata?: Record<string, unknown> }
export type ArtifactFormat = "docx" | "pptx"
export type ArtifactStatus = "queued" | "planning" | "rendering" | "validating" | "ready" | "failed" | "cancelled"
export interface ArtifactRequest { format: ArtifactFormat; template_id: string; use_document_template: boolean }
export interface ArtifactVersion { id: string; version_number: number; status: ArtifactStatus; file_name?: string | null; mime_type?: string | null; size_bytes?: number | null; page_count?: number | null; preview_count: number; qa: Record<string, unknown>; document_template_version_id?: string | null; document_template_snapshot?: Record<string, unknown>; error?: string | null; citations: Citation[]; created_at: string }
export interface Artifact { id: string; conversation_id: string; message_id?: string | null; title: string; format: ArtifactFormat; template_id: string; use_document_template: boolean; status: ArtifactStatus; current_version: number; progress: number; error?: string | null; version?: ArtifactVersion | null; versions: ArtifactVersion[]; created_at: string; updated_at: string }
export type DocumentTemplateStatus = "queued" | "validating" | "ready" | "failed"
export interface DocumentTemplateVersion { id: string; version_number: number; file_name: string; mime_type: string; size_bytes: number; sha256: string; status: DocumentTemplateStatus; progress: number; validation_report: Record<string, unknown>; preview_count: number; uploaded_by: string; activated_at?: string | null; error?: string | null; created_at?: string | null }
export interface OrganizationDocumentTemplate { id?: string | null; enabled: boolean; active_version_id?: string | null; active_version?: DocumentTemplateVersion | null; pending_version?: DocumentTemplateVersion | null; versions: DocumentTemplateVersion[]; can_manage: boolean; created_at?: string | null; updated_at?: string | null }
export interface Message { id: string; role: "user" | "assistant"; content: string; status: "completed" | "streaming" | "error"; created_at: string; attachments?: Attachment[]; knowledge_base_ids?: string[]; web_search_enabled?: boolean; activity?: string; grounding_status?: string; citations?: Citation[]; artifacts?: Artifact[] }
export interface Prompt { id: string; title: string; description?: string | null; body: string; tags: string[]; favorite: boolean; archived: boolean; version_number: number; last_editor: string; updated_at: string }
export interface PromptVersion { id: string; version_number: number; title: string; body: string; created_at: string }
export interface Member { id: string; display_name: string; email: string; role: Role }
export interface Invitation { id: string; email: string; role: Role; status: "pending" | "accepted" | "expired" | "revoked"; expires_at: string; acceptance_token?: string }
export interface UserSettings { custom_instructions: string; theme: "light" | "dark" | "system"; default_model: string; default_effort: Effort; web_search_default: boolean }
export interface ModelOption { id: string; display_name: string; supports_effort: boolean; supports_files: boolean }
export interface AuditEvent { id: string; action: string; target_type: string; target_id: string; metadata: Record<string, unknown>; created_at: string }
export interface KnowledgeDocumentVersion { id: string; version_number: number; file_name: string; mime_type: string; size_bytes: number; extraction_status: string; extraction_quality: string; effective_at?: string | null; authoritative: boolean; created_at: string }
export interface KnowledgeDocument { id: string; knowledge_base_id: string; title: string; current_version: number; archived: boolean; created_by: string; created_at: string; updated_at: string; versions: KnowledgeDocumentVersion[] }
export interface KnowledgeMember { id: string; display_name: string; email: string; reason?: string }
export interface KnowledgeBase { id: string; title: string; description: string; archived: boolean; document_count: number; member_count: number; can_manage: boolean; has_access?: boolean; created_at: string; updated_at: string; documents?: KnowledgeDocument[]; members?: KnowledgeMember[] }
export interface KnowledgeConflict { id: string; knowledge_base_id: string; conflict_type: string; summary: string; left?: { version_id: string; file_name: string; version: number; uploader_id?: string; date?: string; page?: number | null; excerpt?: string | null } | null; right?: { version_id: string; file_name: string; version: number; uploader_id?: string; date?: string; page?: number | null; excerpt?: string | null } | null; created_at: string }
export interface KnowledgeProposal { id: string; knowledge_base_id: string; title: string; content: string; proposed_by: string; created_at: string }
export interface KnowledgeReview { conflicts: KnowledgeConflict[]; proposals: KnowledgeProposal[]; unanswered_questions: Array<{ id: string; question: string; reason: string; conversation_id: string; created_at: string }>; failed_ingestions: Array<{ id: string; version_id: string; error?: string | null; updated_at: string }>; reported_answers: Array<{ id: string; message_id: string; rating: string; note: string; answer: string; created_at: string }>; low_quality_extractions: Array<{ version_id: string; file_name: string; mime_type: string; updated_at: string }> }
export type StreamEvent = { event: string; data: Record<string, unknown> }
