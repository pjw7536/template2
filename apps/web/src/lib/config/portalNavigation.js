import {
  ActivityIcon,
  BookOpenIcon,
  BugIcon,
  GaugeIcon,
  LayoutGridIcon,
  MessageSquareIcon,
  NetworkIcon,
  RadarIcon,
  ScanSearchIcon,
} from "lucide-react"

import { readEnvValue } from "@/lib/runtimeEnv"

function externalLink(title, envKey) {
  const href = readEnvValue(envKey)
  return href ? { title, href, external: true } : null
}

function compactItems(items) {
  return items.filter(Boolean)
}

export const portalNavigationItems = [
  {
    title: "Apps",
    icon: LayoutGridIcon,
    items: compactItems([
      { title: "Appstore", href: "/appstore", appScope: "appstore" },
      { title: "ESOP Dashboard", href: "/esop_dashboard", appScope: "line-dashboard" },
      { title: "Observer", href: "/observer", appScope: "observer" },
      {
        title: "TIP현황",
        href: "/ESOP_Dashboard/tip-status",
        requiredAppScopes: ["line-dashboard", "observer"],
      },
      { title: "메일함", href: "/emails/inbox", appScope: "emails" },
      {
        title: "Spider",
        href: "/spider",
        anyAppScopes: ["l0-spider", "l1-spider", "l3-spider", "pm-spider", "tttm-spider"],
        children: [
          {
            title: "L0 Spider",
            href: "/spider/l0",
            icon: ActivityIcon,
            appScope: "l0-spider",
            external: true,
          },
          {
            title: "L1 Spider",
            href: "/spider/l1",
            icon: RadarIcon,
            appScope: "l1-spider",
            external: true,
          },
          { title: "L3 Spider", href: "/spider/l3", icon: NetworkIcon, appScope: "l3-spider" },
          { title: "TTTM Spider", href: "/spider/tttm", icon: ScanSearchIcon, appScope: "tttm-spider" },
          { title: "PM Spider", href: "/spider/pm", icon: GaugeIcon, appScope: "pm-spider" },
          { title: "Defect Spider", href: "/spider/defect", icon: BugIcon, external: true },
        ],
      },
      { title: "접속 현황", href: "/access-stats", appScope: "access-stats" },
      externalLink("PMx", "VITE_PORTAL_PMX_URL"),
    ]),
  },
  {
    title: "About Us",
    icon: BookOpenIcon,
    items: compactItems([
      { title: "Team", href: "/teamstaff", appScope: "teamstaff" },
      externalLink("Etch MOSAIC", "VITE_PORTAL_MOSAIC_URL"),
      externalLink("Etch Confluence", "VITE_PORTAL_CONFLUENCE_URL"),
    ]),
  },
  {
    title: "Contacts",
    icon: MessageSquareIcon,
    items: [
      { title: "VoE", href: "/voc", appScope: "voc" },
    ],
  },
]
