"use client"

import { BookOpen, Brain, Building2, Check, ChevronDown, ClipboardCheck, Link2, MessageSquarePlus, MoreHorizontal, Plus, Search, Settings2 } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import type { Conversation, Organization, UserProfile, View } from "@/lib/types"
import { BrandMark } from "@/components/app/brand-mark"

interface SidebarProps {
  user: UserProfile
  organizations: Organization[]
  activeOrganizationId: string
  conversations: Conversation[]
  activeConversationId: string
  activeView: View
  onOrganizationChange: (id: string) => void
  onManageOrganizations: () => void
  onSignOut: () => void
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onViewChange: (view: View) => void
  onConversationAction: (id: string, action: "pin" | "archive" | "delete") => void
  onNavigate?: () => void
}

export function AppSidebar(props: SidebarProps) {
  const filtered = props.conversations.filter((conversation) => !conversation.archived)
  const canReviewKnowledge = props.user.role === "owner" || props.user.role === "admin"
  return (
    <aside className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 items-center gap-3 px-4">
        <BrandMark />
        <span className="text-lg font-semibold tracking-tight">Jules AI</span>
      </div>
      <div className="px-3 pb-3">
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" className="h-11 w-full justify-start bg-background/70 px-3" aria-label="Switch organization" />}>
            <Building2 /><span className="min-w-0 flex-1 truncate text-left">{props.organizations.find((organization) => organization.id === props.activeOrganizationId)?.name ?? "Organization"}</span><ChevronDown />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
            <DropdownMenuGroup>{props.organizations.map((organization) => <DropdownMenuItem key={organization.id} onClick={() => props.onOrganizationChange(organization.id)}>{organization.id === props.activeOrganizationId ? <Check /> : <Building2 />}<span className="min-w-0 flex-1 truncate">{organization.name}</span><span className="text-xs capitalize text-muted-foreground">{organization.role}</span></DropdownMenuItem>)}</DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup><DropdownMenuItem onClick={props.onManageOrganizations}><Plus />Create organization</DropdownMenuItem><DropdownMenuItem onClick={props.onManageOrganizations}><Link2 />Join organization</DropdownMenuItem></DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <nav className="flex flex-col gap-1 px-3" aria-label="Main navigation">
        <Button className="h-10 justify-start" onClick={() => { props.onNewChat(); props.onNavigate?.() }}><MessageSquarePlus data-icon="inline-start" />New chat</Button>
        <Button variant="ghost" className="h-10 justify-start" onClick={() => props.onViewChange("chat")}><Search data-icon="inline-start" />Search chats</Button>
        <Button variant={props.activeView === "knowledge" ? "secondary" : "ghost"} className="h-10 justify-start" onClick={() => { props.onViewChange("knowledge"); props.onNavigate?.() }}><Brain data-icon="inline-start" />Knowledge</Button>
        {canReviewKnowledge ? <Button variant={props.activeView === "review" ? "secondary" : "ghost"} className="h-10 justify-start" onClick={() => { props.onViewChange("review"); props.onNavigate?.() }}><ClipboardCheck data-icon="inline-start" />Knowledge Review</Button> : null}
        <Button variant={props.activeView === "prompts" ? "secondary" : "ghost"} className="h-10 justify-start" onClick={() => { props.onViewChange("prompts"); props.onNavigate?.() }}><BookOpen data-icon="inline-start" />Prompt library</Button>
        {props.user.role !== "member" ? <Button variant={props.activeView === "organization" ? "secondary" : "ghost"} className="h-10 justify-start" onClick={() => { props.onViewChange("organization"); props.onNavigate?.() }}><Building2 data-icon="inline-start" />Organization</Button> : null}
      </nav>
      <Separator className="my-3" />
      <div className="px-4 pb-2 text-xs font-medium text-muted-foreground">Today</div>
      <ScrollArea className="min-h-0 flex-1 px-2">
        <div className="flex flex-col gap-0.5 pb-4">
          {filtered.map((conversation) => (
            <div key={conversation.id} className={cn("group flex items-center rounded-lg", props.activeView === "chat" && conversation.id === props.activeConversationId && "bg-sidebar-accent text-sidebar-accent-foreground")}>
              <button className="min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm" onClick={() => { props.onSelectConversation(conversation.id); props.onNavigate?.() }}>{conversation.title}</button>
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" className="mr-1 opacity-0 group-hover:opacity-100 data-[popup-open]:opacity-100" aria-label={`Actions for ${conversation.title}`} />}><MoreHorizontal /></DropdownMenuTrigger>
                <DropdownMenuContent align="end"><DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => props.onConversationAction(conversation.id, "pin")}>{conversation.pinned ? "Unpin" : "Pin"}</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => props.onConversationAction(conversation.id, "archive")}>Archive</DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" onClick={() => props.onConversationAction(conversation.id, "delete")}>Delete</DropdownMenuItem>
                </DropdownMenuGroup></DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="p-3">
        <Button variant={props.activeView === "settings" ? "secondary" : "ghost"} className="mb-2 h-10 w-full justify-start" onClick={() => { props.onViewChange("settings"); props.onNavigate?.() }}><Settings2 data-icon="inline-start" />Settings</Button>
        <DropdownMenu>
          <DropdownMenuTrigger render={<Button variant="outline" className="h-auto w-full justify-start px-2 py-2" />}>
            <Avatar className="size-8"><AvatarFallback>{props.user.display_name.slice(0, 1)}</AvatarFallback></Avatar>
            <span className="min-w-0 flex-1 text-left"><span className="block truncate text-sm font-medium">{props.user.display_name}</span><span className="block truncate text-xs text-muted-foreground">{props.user.email}</span></span>
            <ChevronDown />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56"><DropdownMenuGroup><DropdownMenuItem onClick={() => props.onViewChange("settings")}>Personal settings</DropdownMenuItem><DropdownMenuItem onClick={props.onSignOut}>Sign out</DropdownMenuItem></DropdownMenuGroup></DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  )
}
