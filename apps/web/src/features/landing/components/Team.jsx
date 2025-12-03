import { useEffect, useRef, useState } from 'react'
import { FacebookIcon, GithubIcon, InstagramIcon, TwitterIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from '@/components/ui/card'

import { cn } from '@/lib/utils'

const TeamMemberCard = ({ member, index, isWide }) => {
  const ref = useRef(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
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
        transitionDelay: `${index * 0.1}s` // ⭐ index 기반 stagger
      }}
      className={cn(
        'group relative border-none pt-24 shadow-none sm:max-lg:col-span-2 transition-all duration-700 ease-out',
        isWide && 'sm:max-lg:col-span-3',
        member.bgColor,
        !isVisible && 'opacity-0 translate-y-6',
        isVisible && 'opacity-100 translate-y-0'
      )}
    >
      <CardContent
        className='border-card bg-card absolute -top-15 left-1/2 w-fit -translate-x-1/2 rounded-full border-6 p-0 transition-all duration-300 group-hover:shadow-xl'
      >
        <div
          className={cn('size-30 overflow-hidden rounded-full pt-4', member.avatarBg)}
        >
          <img src={member.image} alt={member.alt} className='h-auto w-full' />
        </div>
      </CardContent>

      <CardHeader className='text-center'>
        <CardTitle className='text-lg'>{member.name}</CardTitle>
        <CardDescription className='text-base font-medium'>
          {member.role}
        </CardDescription>
      </CardHeader>

      <CardFooter className='flex h-5.5 justify-center gap-3'>
        <a
          href={member.socialLinks.facebook}
          className={cn('transition-colors duration-300', member.socialLinkColor)}
        >
          <FacebookIcon className='size-5' />
        </a>
        <a
          href={member.socialLinks.twitter}
          className={cn('transition-colors duration-300', member.socialLinkColor)}
        >
          <TwitterIcon className='size-5' />
        </a>
        <a
          href={member.socialLinks.github}
          className={cn('transition-colors duration-300', member.socialLinkColor)}
        >
          <GithubIcon className='size-5' />
        </a>
        <a
          href={member.socialLinks.instagram}
          className={cn('transition-colors duration-300', member.socialLinkColor)}
        >
          <InstagramIcon className='size-5' />
        </a>
      </CardFooter>
    </Card>
  )
}

const Team = ({ teamMembers }) => {
  return (
    <section className='py-8 sm:py-16 lg:py-24'>
      <div className='mx-auto max-w-7xl px-4 sm:px-6 lg:px-8'>
        <div className='mb-20 space-y-4 text-center lg:mb-24'>
          <div>
            <Badge variant='outline' className='text-sm font-normal'>
              Creative team
            </Badge>
          </div>
          <h2 className='text-2xl font-semibold md:text-3xl lg:text-4xl'>
            Meet the Brilliant Minds Behind Our Success
          </h2>
          <p className='text-muted-foreground text-xl'>
            A passionate team of innovators, creators, and problem-solvers working together to make an impact.
          </p>
        </div>

        {/* Team Members */}
        <div className='grid gap-x-6 gap-y-20 sm:grid-cols-6 lg:grid-cols-5'>
          {teamMembers.map((member, index) => {
            const isWide = index >= teamMembers.length - 2
            return (
              <TeamMemberCard
                key={index}
                member={member}
                index={index}
                isWide={isWide}
              />
            )
          })}
        </div>
      </div>
    </section>
  )
}

export default Team
