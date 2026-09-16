export function MembersSummaryCards({ items }) {
  return (
    <div className="grid gap-3 md:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon

        return (
          <div key={item.label} className="rounded-lg border bg-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted-foreground">{item.label}</p>
                <p className="mt-1 truncate text-xl font-semibold tabular-nums text-foreground">
                  {item.value}
                </p>
              </div>
              <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-2 truncate text-xs text-muted-foreground">{item.description}</p>
          </div>
        )
      })}
    </div>
  )
}
