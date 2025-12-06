import { useEffect, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
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
        transitionDelay: `${index * 0.1}s`
      }}
      className={cn(
        // pt를 줄여서 전체 카드 높이 살짝 축소
        'group relative border-none pt-16 shadow-none sm:max-lg:col-span-2 transition-all duration-700 ease-out',
        isWide && 'sm:max-lg:col-span-3',
        member.bgColor,
        !isVisible && 'opacity-0 translate-y-6',
        isVisible && 'opacity-100 translate-y-0'
      )}
    >
      <CardContent
        className='border-card bg-card absolute -top-12 left-1/2 w-fit -translate-x-1/2 rounded-full border-4 p-0 transition-all duration-300 group-hover:shadow-xl'
      >
        <div
          // 아바타 사이즈와 안쪽 패딩 줄이기
          className={cn('size-24 overflow-hidden rounded-full', member.avatarBg)}
        >
          <img src={member.image} alt={member.alt} className='h-auto w-full' />
        </div>
      </CardContent>

      <CardHeader className='text-center'>
        {/* 이름 폰트 한 단계 축소 */}
        <CardTitle className='text-base font-semibold'>
          {member.name}
        </CardTitle>
        {/* 역할 폰트도 한 단계 축소 */}
        <CardDescription className='text-sm font-medium'>
          {member.role}
        </CardDescription>
      </CardHeader>
    </Card>
  )
}


const Team = ({ teamMembers }) => {
  return (
    <section className='py-8 sm:py-16 lg:py-24'>
      <div className='mx-auto max-w-5xl px-4 sm:px-6 lg:px-8'>
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
            서로의 아이디어를 연결해, 작은 변화도 의미 있게 만드는 일을 이어가고 있습니다.
          </p>
        </div>

        {/* Team Members */}
        <div className='grid gap-x-6 gap-y-20 sm:grid-cols-6 lg:grid-cols-7'>
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
