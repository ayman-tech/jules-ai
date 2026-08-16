import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { PromptPickerDialog } from "@/components/app/prompt-picker-dialog"
import type { Prompt } from "@/lib/types"

const prompt: Prompt = {
  id: "prompt-1",
  title: "Market review",
  description: "Evaluate a market for a reporting period.",
  body: "Research {{company_name}} for {{reporting_period}}.",
  tags: ["Strategy"],
  favorite: true,
  archived: false,
  version_number: 2,
  last_editor: "Ayman",
  updated_at: "2026-08-16T00:00:00Z",
}

describe("PromptPickerDialog", () => {
  it("previews, fills, and inserts a prompt without navigating", () => {
    const onUsePrompt = vi.fn(() => true)
    const onOpenChange = vi.fn()
    render(<PromptPickerDialog open prompts={[prompt]} onOpenChange={onOpenChange} onUsePrompt={onUsePrompt} onFavorite={vi.fn()} onManagePrompts={vi.fn()} />)

    expect(screen.getByRole("heading", { name: "Choose a prompt" })).toBeDefined()
    fireEvent.click(screen.getByRole("button", { name: "Select prompt Market review" }))
    fireEvent.change(screen.getByLabelText("Company name"), { target: { value: "Northstar" } })
    fireEvent.change(screen.getByLabelText("Reporting period"), { target: { value: "Q3 2026" } })
    fireEvent.click(screen.getByRole("button", { name: "Use prompt" }))

    expect(onUsePrompt).toHaveBeenCalledWith("Research Northstar for Q3 2026.")
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("keeps the overlay open when replacing the current draft is declined", () => {
    const onOpenChange = vi.fn()
    render(<PromptPickerDialog open prompts={[{ ...prompt, body: "Run the review." }]} onOpenChange={onOpenChange} onUsePrompt={() => false} onFavorite={vi.fn()} onManagePrompts={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: "Select prompt Market review" }))
    fireEvent.click(screen.getByRole("button", { name: "Use prompt" }))

    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(screen.getByRole("heading", { name: "Choose a prompt" })).toBeDefined()
  })
})
