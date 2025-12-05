import ErrorPage04 from "@/features/errors/components/ErrorPage04"

export function NotFoundPage() {
  return (
    <ErrorPage04
      title="Page not found"
      description="The page you are looking for does not exist or has been moved."
      actionLabel="Back to home page"
      homeHref="/"
    />
  )
}
