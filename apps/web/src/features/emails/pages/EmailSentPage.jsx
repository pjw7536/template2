import { EmailInboxView } from "../components/EmailInboxView"
import { useEmailSentController } from "../hooks/useEmailInboxController"

export function EmailSentPage() {
  const controller = useEmailSentController()
  return <EmailInboxView {...controller} />
}
