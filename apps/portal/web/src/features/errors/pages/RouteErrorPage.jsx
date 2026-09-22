import { useRouteError } from "react-router-dom"

import ErrorPage04 from "../components/ErrorPage04"
import { normalizeRouteError } from "../utils/routeError"

export function RouteErrorPage() {
  const error = useRouteError()
  const { title, description, statusLabel } = normalizeRouteError(error)

  return (
    <ErrorPage04
      title={title}
      description={description}
      statusLabel={statusLabel}
      actionLabel="Back to home page"
      homeHref="/"
    />
  )
}
