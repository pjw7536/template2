import HeroSection from "../components/HeroSection"
import AppIntegrationMarquee from "../components/AppIntegrationMarquee"
import Team from "../components/Team"
import { PopularServicesSection } from "../components/PopularSection"
import { marqueeApps, teamMembers } from "../constants"

const DEFAULT_HERO_ACTIONS = [
  { label: "대시보드로 이동", href: "/ESOP_Dashboard" },
  { label: "Appstore 둘러보기", href: "/landing/appstore", variant: "outline" },
]

const LandingPage = ({ heroActions = DEFAULT_HERO_ACTIONS }) => {
  return (
    <>
      <HeroSection actions={heroActions} />
      <PopularServicesSection />
      <Team teamMembers={teamMembers} />
      <AppIntegrationMarquee apps={marqueeApps} />
    </>
  )
}

export default LandingPage
