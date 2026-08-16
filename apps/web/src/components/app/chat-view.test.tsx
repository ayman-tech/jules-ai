import { act, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ArtifactCard, ChatView } from "@/components/app/chat-view"
import { julesApi } from "@/lib/api"
import type { Artifact, ArtifactRequest } from "@/lib/types"

vi.mock("@/lib/api", () => ({
  julesApi: {
    artifact: vi.fn(),
    retryArtifact: vi.fn(),
    cancelArtifact: vi.fn(),
    deleteArtifact: vi.fn(),
  },
}))

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const queued: Artifact = {
  id: "artifact-1",
  conversation_id: "conversation-1",
  message_id: "message-1",
  title: "Market research",
  format: "docx",
  template_id: "general-document",
  use_document_template: false,
  status: "queued",
  current_version: 1,
  progress: 0,
  versions: [],
  created_at: "2026-08-15T00:00:00Z",
  updated_at: "2026-08-15T00:00:00Z",
}

describe("ArtifactCard polling", () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it("resumes a queued artifact after mount and tolerates a temporary request failure", async () => {
    const ready = { ...queued, status: "ready" as const, progress: 100 }
    vi.mocked(julesApi.artifact).mockRejectedValueOnce(new Error("temporary")).mockResolvedValueOnce(ready)
    const onUpdated = vi.fn()

    render(<ArtifactCard artifact={queued} organizationId="organization-1" knowledgeBases={[]} onUpdated={onUpdated} onDeleted={vi.fn()} />)
    expect(screen.getByText("Queued")).toBeDefined()

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
    expect(onUpdated).not.toHaveBeenCalled()

    await act(async () => { await vi.advanceTimersByTimeAsync(4_000) })
    expect(onUpdated).toHaveBeenCalledWith(ready)
    expect(julesApi.artifact).toHaveBeenCalledTimes(2)

    await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
    expect(julesApi.artifact).toHaveBeenCalledTimes(2)
  })
})

describe("Deep research composer toggle", () => {
  it("is available for chat, documents, and presentations", () => {
    const onDeepResearchChange = vi.fn()
    const baseProps = {
      conversation: { id: "conversation-1", title: "New conversation", model: "gemini-test", effort: "medium" as const, pinned: false, archived: false, knowledge_base_ids: [], web_search_enabled: false, updated_at: "2026-08-15T00:00:00Z" },
      organizationId: "organization-1",
      messages: [],
      models: [{ id: "gemini-test", display_name: "Gemini Test", supports_effort: true, supports_files: true }],
      draft: "Research this topic",
      effort: "medium" as const,
      model: "gemini-test",
      knowledgeBases: [],
      selectedKnowledgeBaseIds: [],
      webSearchEnabled: false,
      deepResearchEnabled: false,
      pendingAttachments: [],
      streaming: false,
      onDraftChange: vi.fn(),
      onEffortChange: vi.fn(),
      onModelChange: vi.fn(),
      onKnowledgeBaseIdsChange: vi.fn(),
      onWebSearchChange: vi.fn(),
      onDeepResearchChange,
      onArtifactRequestChange: vi.fn(),
      onArtifactUpdated: vi.fn(),
      onArtifactDeleted: vi.fn(),
      onSend: vi.fn(),
      onStop: vi.fn(),
      onOpenPrompts: vi.fn(),
      onFileSelect: vi.fn(),
      onRemoveAttachment: vi.fn(),
      onOpenMobileNavigation: vi.fn(),
      onRegenerate: vi.fn(),
      onSaveKnowledge: vi.fn(),
      onReportAnswer: vi.fn(),
    }
    const { rerender } = render(<ChatView {...baseProps} />)

    fireEvent.click(screen.getByRole("button", { name: "Enable deep research" }))
    expect(onDeepResearchChange).toHaveBeenCalledWith(true)

    for (const artifactRequest of [
      { format: "docx", template_id: "auto", use_document_template: true },
      { format: "pptx", template_id: "auto", use_document_template: false },
    ] satisfies ArtifactRequest[]) {
      rerender(<ChatView {...baseProps} artifactRequest={artifactRequest} />)
      expect(screen.getByRole("button", { name: "Enable deep research" })).toBeDefined()
    }
  })
})
