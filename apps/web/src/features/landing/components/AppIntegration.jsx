import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRightIcon } from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardTitle } from '@/components/ui/card'

import { cn } from '@/lib/utils'


const AppCard = ({ app, index }) => {
  const ref = useRef(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true)
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.1 }
    )

    if (ref.current) observer.observe(ref.current)

    return () => observer.disconnect()
  }, [])

  return (
    <Card
      ref={ref}
      style={{
        transitionDelay: `${index * 0.1}s`, // ⭐ index 기반 stagger
      }}
      className={cn(
        'hover:bg-muted group border-none shadow-none transition-all duration-700 ease-out',
        !isVisible && 'opacity-0 translate-y-6',
        isVisible && 'opacity-100 translate-y-0'
      )}
    >
      <CardContent className='flex flex-col gap-6'>
        <Avatar className='size-12 rounded-lg'>
          <AvatarFallback className={cn('rounded-lg', app.bgColor)}>
            <img src={app.image} alt={app.name} className='size-7 object-contain' />
          </AvatarFallback>
        </Avatar>

        <div>
          <CardTitle className='mb-3.5 text-2xl font-medium'>{app.name}</CardTitle>
          <CardDescription className='text-xl'>{app.description}</CardDescription>
        </div>

        <Button variant='outline' asChild className='h-7 w-fit gap-1.5 px-2 py-1 text-xs'>
          <a href={app.link}>
            Connect
            <ChevronRightIcon className='transition-transform group-hover:translate-x-1' />
          </a>
        </Button>
      </CardContent>
    </Card>
  )
}



const AppIntegration = ({ partnerApps }) => {
  return (
    <section className='py-8 sm:py-16 lg:py-24'>
      <div className='mx-auto max-w-7xl px-4 sm:px-6 lg:px-8'>

        {/* Header */}
        <div className='mb-12 space-y-4 text-center sm:mb-16 lg:mb-24'>
          <p className='text-primary text-sm font-medium uppercase'>App Integration</p>
          <h2 className='text-2xl font-semibold md:text-3xl lg:text-4xl'>Browse our partner apps</h2>
          <p className='text-muted-foreground text-xl'>
            Explore integrated apps that enhance productivity, streamline workflows, and simplify collaboration effortlessly.
          </p>
          <Button size='lg' asChild className='rounded-lg text-base'>
            <Link to='/appstore'>Browse All Apps</Link>
          </Button>
        </div>

        {/* App Cards */}
        <div className='grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4'>
          {partnerApps.map((app, index) => (
            <AppCard key={index} app={app} index={index} />
          ))}
        </div>
      </div>
    </section>
  )
}

export default AppIntegration
