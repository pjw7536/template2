import { useEffect } from "react"
import { isRouteErrorResponse, useRouteError } from "react-router-dom"

import ErrorPage04 from "../components/ErrorPage04"

export function RouteErrorPage() {
  const error = useRouteError()
  const isNotFound = isRouteErrorResponse(error) && error.status === 404

  useEffect(() => {
    if (error) {
      console.error("Unhandled route error", error)
    }
  }, [error])

  const title = isNotFound ? "Page not found" : "Something went wrong"
  const description = isNotFound
    ? "The page you are looking for does not exist or has been moved."
    : "An unexpected error occurred. Please try again or head back home."

  return (
    <ErrorPage04
      title={title}
      description={description}
      actionLabel="Back to home page"
      homeHref="/"
    />
  )
}
