"use client"

import { OrganizationAccess } from "@/components/organizations/organization-access"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { Organization } from "@/lib/types"

export function OrganizationAccessDialog({ open, onOpenChange, onOrganizationReady }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onOrganizationReady: (organization: Organization) => void
}) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
      <DialogHeader><DialogTitle>Organizations</DialogTitle><DialogDescription>Create another workspace or join one with an invitation.</DialogDescription></DialogHeader>
      <OrganizationAccess compact onOrganizationReady={(organization) => { onOpenChange(false); onOrganizationReady(organization) }} />
    </DialogContent>
  </Dialog>
}
