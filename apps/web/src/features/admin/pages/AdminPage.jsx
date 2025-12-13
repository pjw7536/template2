import { Link, Navigate } from "react-router-dom"
import { ShieldIcon } from "lucide-react"

import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function AdminPage() {
  const { user } = useAuth()
  const isSuperuser = Boolean(user?.is_superuser)

  if (!isSuperuser) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold">Admin</h1>
          <p className="text-muted-foreground text-sm">Superuser tools</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="gap-1">
            <CardTitle className="flex items-center gap-2">
              <ShieldIcon className="size-4" />
              UNASSIGNED mailbox
            </CardTitle>
            <CardDescription>
              Emails that arrived before sender/user mapping was available.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-4">
            <div className="text-muted-foreground text-sm">
              View and manage mails in the UNASSIGNED mailbox.
            </div>
            <Button asChild>
              <Link to="/emails?mailbox=UNASSIGNED">Open</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

