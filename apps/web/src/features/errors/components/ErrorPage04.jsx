import { Link } from "react-router-dom"

import Error04Illustration from "@/assets/svg/error-04-illustration"
import { Button } from "@/components/ui/button"

function ErrorPage04({
  title = "Page not found",
  description = "We couldn't find the page you are looking for.",
  actionLabel = "Back to home page",
  homeHref = "/",
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-12 px-8 py-8 sm:py-16 lg:justify-between lg:py-24">
      <Error04Illustration aria-hidden="true" className="h-[clamp(300px,50vh,600px)]" />
      <div className="text-center">
        <h1 className="mb-1.5 text-2xl font-semibold">{title}</h1>
        <p className="mb-5 text-muted-foreground">{description}</p>
        <Button size="lg" className="rounded-lg text-base" asChild>
          <Link to={homeHref}>{actionLabel}</Link>
        </Button>
      </div>
    </div>
  )
}

export default ErrorPage04
