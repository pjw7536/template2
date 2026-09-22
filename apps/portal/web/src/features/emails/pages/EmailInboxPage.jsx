import { EmailInboxView } from "../components/EmailInboxView"
import { useEmailInboxController } from "../hooks/useEmailInboxController"

export function EmailInboxPage() {
  const controller = useEmailInboxController()
  return <EmailInboxView {...controller} />
}
