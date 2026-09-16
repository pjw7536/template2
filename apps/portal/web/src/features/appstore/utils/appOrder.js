export function moveAppInOrder(apps, fromIndex, toIndex) {
  if (!Array.isArray(apps)) return []
  if (fromIndex < 0 || fromIndex >= apps.length) return apps
  if (toIndex < 0 || toIndex >= apps.length || fromIndex === toIndex) return apps

  const nextApps = [...apps]
  const [movedApp] = nextApps.splice(fromIndex, 1)
  nextApps.splice(toIndex, 0, movedApp)
  return nextApps
}

export function hasAppOrderChanged(initialApps, draftApps) {
  if (!Array.isArray(initialApps) || !Array.isArray(draftApps)) return false
  if (initialApps.length !== draftApps.length) return true
  return initialApps.some((app, index) => app.id !== draftApps[index]?.id)
}

export function moveAppById(apps, sourceAppId, targetAppId) {
  if (!Array.isArray(apps)) return []
  const fromIndex = apps.findIndex((app) => app.id === sourceAppId)
  const toIndex = apps.findIndex((app) => app.id === targetAppId)
  return moveAppInOrder(apps, fromIndex, toIndex)
}

export function moveAppWithinCategory(apps, sourceAppId, targetAppId, category) {
  if (!Array.isArray(apps)) return []
  if (category === "all") return moveAppById(apps, sourceAppId, targetAppId)

  const matchesCategory = (app) => (app.category || "기타") === category
  const categoryApps = apps.filter(matchesCategory)
  const reorderedApps = moveAppById(categoryApps, sourceAppId, targetAppId)
  if (reorderedApps === categoryApps) return apps

  let categoryIndex = 0
  return apps.map((app) =>
    matchesCategory(app) ? reorderedApps[categoryIndex++] : app,
  )
}
