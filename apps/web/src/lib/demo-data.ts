import type { AuditEvent, Conversation, Invitation, KnowledgeBase, KnowledgeReview, Member, Message, ModelOption, Organization, Prompt, UserProfile, UserSettings } from "@/lib/types"

export const demoUser: UserProfile = { id: "user-ayman", display_name: "Ayman", email: "ayman@northstaradvisory.com", role: "owner", active_organization_id: "org-northstar" }
export const demoOrganizations: Organization[] = [
  { id: "org-northstar", name: "Northstar Advisory", slug: "northstar-advisory", role: "owner" },
  { id: "org-meridian", name: "Meridian Labs", slug: "meridian-labs", role: "admin" },
]
export const demoConversations: Conversation[] = [
  { id: "conversation-quarterly", title: "Quarterly planning brief", model: "gemini-3.1-pro-preview", effort: "high", pinned: true, archived: false, knowledge_base_ids: ["kb-operations", "kb-finance"], web_search_enabled: false, updated_at: new Date().toISOString() },
  { id: "conversation-board", title: "Board memo synthesis", model: "gemini-3.1-pro-preview", effort: "medium", pinned: false, archived: false, knowledge_base_ids: ["kb-operations", "kb-finance"], web_search_enabled: false, updated_at: new Date(Date.now() - 36e5).toISOString() },
  { id: "conversation-vendor", title: "Vendor risk review", model: "gemini-3.5-flash", effort: "medium", pinned: false, archived: false, knowledge_base_ids: ["kb-operations"], web_search_enabled: true, updated_at: new Date(Date.now() - 72e5).toISOString() },
]
export const demoMessages: Record<string, Message[]> = {
  "conversation-quarterly": [
    { id: "message-user-1", role: "user", content: "Summarize the top three priorities for Q3 from our operating plan.", status: "completed", created_at: new Date(Date.now() - 12e5).toISOString(), attachments: [{ id: "attachment-1", file_name: "Q3-operating-plan.pdf", mime_type: "application/pdf", size_bytes: 1_258_291, scan_status: "clean" }] },
    { id: "message-assistant-1", role: "assistant", content: "### Q3 priorities\n\n1. **Drive revenue growth in core segments.** Focus investment on the strongest professional-services and technology-advisory opportunities.\n\n2. **Improve operating efficiency.** Standardize repeatable workflows, reduce cost-to-serve, and make ownership visible.\n\n3. **Strengthen risk and compliance.** Tighten vendor oversight and data-governance readiness before the next planning cycle.\n\nThe plan is strongest when each priority has one accountable owner and a measurable quarterly checkpoint.", status: "completed", created_at: new Date(Date.now() - 9e5).toISOString() },
  ],
  "conversation-board": [], "conversation-vendor": [],
}
export const demoPrompts: Prompt[] = [
  { id: "prompt-1", title: "Executive summary", description: "Turn a long business document into a concise leadership brief.", body: "Act as a strategy advisor. Review the material for {{company_name}} during {{reporting_period}} and create a concise executive summary for senior leaders. Highlight trends, risks, opportunities, and recommendations.", tags: ["Strategy", "Leadership"], favorite: true, archived: false, version_number: 4, last_editor: "Maya Chen", updated_at: new Date(Date.now() - 2 * 864e5).toISOString() },
  { id: "prompt-2", title: "Competitor analysis", description: "Compare competitors using a consistent decision framework.", body: "Analyze the named competitors across positioning, strengths, weaknesses, pricing, and strategic risk. End with three recommended moves.", tags: ["Research"], favorite: false, archived: false, version_number: 2, last_editor: "Ayman", updated_at: new Date(Date.now() - 4 * 864e5).toISOString() },
  { id: "prompt-3", title: "Meeting follow-up", description: "Convert meeting notes into decisions and accountable actions.", body: "Turn these meeting notes into decisions, open questions, action items, owners, and deadlines.", tags: ["Operations"], favorite: false, archived: false, version_number: 3, last_editor: "Maya Chen", updated_at: new Date(Date.now() - 5 * 864e5).toISOString() },
  { id: "prompt-4", title: "Risk register review", description: "Challenge a risk register and identify missing controls.", body: "Review the risk register. Flag material gaps, ambiguous owners, weak controls, and overdue mitigations. Prioritize the top five changes.", tags: ["Risk"], favorite: false, archived: false, version_number: 1, last_editor: "Ayman", updated_at: new Date(Date.now() - 7 * 864e5).toISOString() },
]
export const demoSettings: UserSettings = { custom_instructions: "Write for a business audience and make next actions explicit.", theme: "system", default_model: "gemini-3.5-flash", default_effort: "medium", web_search_default: true }
export const demoModels: ModelOption[] = [
  { id: "gemini-3.5-flash", display_name: "Default", supports_effort: true, supports_files: true },
  { id: "gemini-3.1-pro-preview", display_name: "Pro", supports_effort: true, supports_files: true },
]
export const demoMembers: Member[] = [
  { id: "user-ayman", display_name: "Ayman", email: "ayman@northstaradvisory.com", role: "owner" },
  { id: "user-maya", display_name: "Maya Chen", email: "maya@northstaradvisory.com", role: "admin" },
  { id: "user-jon", display_name: "Jon Bell", email: "jon@northstaradvisory.com", role: "member" },
]
export const demoInvitations: Invitation[] = [{ id: "invite-1", email: "priya@northstaradvisory.com", role: "member", status: "pending", expires_at: new Date(Date.now() + 5 * 864e5).toISOString() }]
export const demoAuditEvents: AuditEvent[] = [
  { id: "audit-1", action: "prompt.updated", target_type: "prompt", target_id: "prompt-1", metadata: { version: 4 }, created_at: new Date(Date.now() - 2 * 864e5).toISOString() },
  { id: "audit-2", action: "invitation.created", target_type: "invitation", target_id: "invite-1", metadata: { email: "priya@northstaradvisory.com" }, created_at: new Date(Date.now() - 3 * 864e5).toISOString() },
]
export const demoKnowledgeBases: KnowledgeBase[] = [
  { id: "kb-operations", title: "Operations", description: "Operating practices, decisions, and team playbooks.", archived: false, document_count: 2, member_count: 3, can_manage: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), documents: [] },
  { id: "kb-finance", title: "Finance", description: "Budgets, controls, forecasts, and finance policies.", archived: false, document_count: 1, member_count: 2, can_manage: true, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), documents: [] },
]
export const demoKnowledgeReview: KnowledgeReview = { conflicts: [], proposals: [], unanswered_questions: [], failed_ingestions: [], reported_answers: [], low_quality_extractions: [] }
