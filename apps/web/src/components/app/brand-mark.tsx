import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export function BrandMark({ className }: { className?: string }) {
  return <span className={cn("flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground", className)} aria-hidden="true"><Sparkles /></span>
}
