import type { Message } from "@/lib/types"

export function reconcileConversationMessages(current: Message[], incoming: Message[], preserveAfterFailure = false): Message[] {
  if (preserveAfterFailure || current.some((message) => message.status === "streaming")) return current
  return incoming
}
