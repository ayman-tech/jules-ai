import { act, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ArtifactCard } from "@/components/app/chat-view"
import { julesApi } from "@/lib/api"
import type { Artifact } from "@/lib/types"

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
