import { describe, expect, it } from "vitest"
import { reconcileConversationMessages } from "@/lib/conversation-state"
import type { Message } from "@/lib/types"

const incoming: Message[] = [{ id: "server-user", role: "user", content: "Saved", status: "completed", created_at: "2026-08-15T00:00:00Z" }]

describe("reconcileConversationMessages", () => {
  it("does not let a stale conversation load erase optimistic streaming messages", () => {
    const current: Message[] = [
      { id: "local-user", role: "user", content: "Create a DOCX", status: "completed", created_at: "2026-08-15T00:00:00Z" },
      { id: "local-assistant", role: "assistant", content: "", status: "streaming", created_at: "2026-08-15T00:00:01Z" },
    ]

    expect(reconcileConversationMessages(current, [])).toBe(current)
  })

  it("preserves an actionable local error once after a failed stream", () => {
    const current: Message[] = [{ id: "local-error", role: "assistant", content: "Please try again.", status: "error", created_at: "2026-08-15T00:00:00Z" }]
    expect(reconcileConversationMessages(current, incoming, true)).toBe(current)
  })

  it("uses authoritative server messages after a successful stream", () => {
    const current: Message[] = [{ id: "local-user", role: "user", content: "Draft", status: "completed", created_at: "2026-08-15T00:00:00Z" }]
    expect(reconcileConversationMessages(current, incoming)).toBe(incoming)
  })
})
