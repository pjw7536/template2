// src/routes/pages/NotFoundPage.jsx
import { Link } from "react-router-dom"

export function NotFoundPage() {
  return (
    <section className="rounded-xl border bg-card p-6 text-center shadow-sm">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        The page you are looking for does not exist.
      </p>
      <div className="mt-4">
        <Link className="text-sm font-medium text-primary hover:underline" to="/">
          Go back home
        </Link>
      </div>
    </section>
  )
}
