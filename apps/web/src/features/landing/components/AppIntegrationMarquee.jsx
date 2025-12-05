import { Marquee } from '@/components/ui/marquee'

import IntegrationCard from './IntegrationCard'

const AppIntegrationMarquee = ({
  apps
}) => {
  return (
    <section className='py-8 sm:py-16 lg:py-24'>
      <div className='mx-auto max-w-7xl px-4 sm:px-6 lg:px-8'>
        {/* Header */}
        <div className='text-center mb-12 space-y-4 sm:mb-12 lg:mb-12'>
          <h2 className='text-xl font-semibold md:text-3xl lg:text-4xl'>Building the future with industry leaders</h2>
          <p className='text-muted-foreground text-xl'>Join 50,000+ companies transforming their industries with us.</p>
        </div>
      </div>
      {/* Marquee */}
      <div className='w-full overflow-hidden'>
        <Marquee pauseOnHover duration={25} gap={1.5}>
          {apps.slice(0, 5).map((app, index) => (
            <IntegrationCard key={index} app={app} />
          ))}
        </Marquee>
      </div>
      <div className='w-full overflow-hidden'>
        <Marquee pauseOnHover duration={25} gap={1.5} reverse>
          {apps.slice(5).map((app, index) => (
            <IntegrationCard key={index} app={app} />
          ))}
        </Marquee>
      </div>
    </section>
  );
}

export default AppIntegrationMarquee
