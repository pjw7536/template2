import { lazy } from "react"

export function lazyNamed(importer, exportName) {
  return lazy(async () => {
    const module = await importer()
    const component = module[exportName]
    if (!component) {
      throw new Error(`Missing lazy export: ${exportName}`)
    }
    return { default: component }
  })
}
