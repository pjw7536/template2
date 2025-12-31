import { useEffect, useState } from "react"

import { buildLineSwitcherOptions, useLineOptionsQuery } from "@/lib/affiliation"
import { TeamSwitcher } from "./TeamSwitcher"

export function LineSwitcherHeader({ menuLabel, manageLabel, ariaLabel }) {
  const { data: lineOptions = [] } = useLineOptionsQuery()
  const options = buildLineSwitcherOptions(lineOptions)
  const [activeId, setActiveId] = useState("")

  useEffect(() => {
    if (!options.length) {
      if (activeId) setActiveId("")
      return
    }

    const hasActive = options.some((option) => option.id === activeId)
    if (!hasActive) {
      setActiveId(options[0].id)
    }
  }, [activeId, options])

  const handleSelect = (nextId) => {
    setActiveId(nextId)
  }

  return (
    <TeamSwitcher
      options={options}
      activeId={activeId}
      onSelect={handleSelect}
      menuLabel={menuLabel}
      manageLabel={manageLabel}
      ariaLabel={ariaLabel}
    />
  )
}
