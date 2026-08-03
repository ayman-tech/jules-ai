import { InviteScreen } from "@/components/auth/invite-screen"

export default async function InvitationPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params
  return <InviteScreen token={token} />
}
