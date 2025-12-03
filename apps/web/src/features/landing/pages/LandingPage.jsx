import HeroSection from '../components/HeroSection'
import Navbar from '../components/Navbar'
import Team from '../components/Team'
import AppIntegration from '../components/AppIntegration'
import AppIntegrationMarquee from '../components/AppIntegrationMarquee'
import { marqueeApps, navigationItems, partnerApps, teamMembers } from '../constants'


const LandingPage = () => {
  return (
    <div className='bg-background min-h-screen'>
      <Navbar navigationItems={navigationItems} />
      <main>
        <HeroSection />
        <AppIntegration partnerApps={partnerApps} />
        <Team teamMembers={teamMembers} />
        <AppIntegrationMarquee apps={marqueeApps} />
      </main>
    </div>
  )
}

export default LandingPage
