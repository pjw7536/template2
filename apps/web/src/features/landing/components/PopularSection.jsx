import { ChartNoAxesCombined, Factory, MailPlus, ShieldCheck } from 'lucide-react'
import { motion } from 'framer-motion'

import { Badge } from '@/components/ui/badge'

const popularServices = [
  {
    icon: Factory,
    title: 'EQP Management',
    subtitle: 'Workspace AIO, Onwafer Viwer, E-TOSS',
    category: 'System',
    popular: true
  },
  {
    icon: ShieldCheck,
    title: 'Quality Management',
    subtitle: 'Spider, Observer, Boda',
    category: 'System',
    popular: true
  },
  {
    icon: ChartNoAxesCombined,
    title: 'Etch Report',
    subtitle: '생산현황, Setup현황, 배기장치전검',
    category: 'Report',
    popular: false
  },
  {
    icon: MailPlus,
    title: 'Etch Support',
    subtitle: '자동화 업무문의 & 지원',
    category: 'VOE',
    popular: false
  }
]

// ------------------------------------------------------
// 🔶 재사용 가능한 UnifiedCard 컴포넌트
// ------------------------------------------------------
export const UnifiedCard = ({ children, className = '', hover = true, variant = 'default' }) => {
  const baseClasses =
    'bg-card dark:bg-card border border-border/50 rounded-2xl p-6 shadow-sm transition-all duration-300'
  const hoverClasses = hover ? 'hover:shadow-lg hover:border-primary/20 hover:-translate-y-1' : ''

  const variantClasses = {
    service: 'min-h-[160px] flex flex-col',
    stat: 'min-h-[160px] flex flex-col justify-center text-center',
    trust: 'min-h-[80px] flex flex-col justify-center p-3',
    default: ''
  }

  return (
    <div className={`${baseClasses} ${hoverClasses} ${variantClasses[variant]} ${className}`}>
      {children}
    </div>
  )
}

// ------------------------------------------------------
// 🔶 Popular Services Grid (HeroSection에서 떼어낸 버전)
// ------------------------------------------------------
export function PopularServicesSection() {
  return (
    <section className='py-8 sm:py-10 lg:py-12'>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.3 }}
        className='mx-auto w-full max-w-5xl px-4 sm:px-6 lg:px-8'
      >
        <div className='grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4'>
          {popularServices.map((service, index) => (
            <motion.div
              key={service.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.4 + index * 0.1 }}
              whileHover={{
                y: -4,
                scale: 1.02,
                transition: { duration: 0.2 }
              }}
              className='group relative h-full cursor-pointer'
            >
              <UnifiedCard variant='service' className='relative h-full'>
                {service.popular && (
                  <Badge className='absolute -top-2 -right-2 z-10 border border-primary/20 bg-primary/10 px-2 py-1 text-xs font-medium text-primary'>
                    Popular
                  </Badge>
                )}

                <div className='mb-4 flex size-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 transition-all duration-300 group-hover:border-primary/30 group-hover:bg-primary/15'>
                  <service.icon className='size-6 text-primary' />
                </div>

                <div className='flex flex-1 flex-col justify-between text-left'>
                  <div>
                    <h4 className='mb-2 text-base font-semibold leading-tight text-foreground transition-colors group-hover:text-primary'>
                      {service.title}
                    </h4>
                    <p className='mb-3 text-sm leading-relaxed text-muted-foreground'>
                      {service.subtitle}
                    </p>
                  </div>

                  <div className='text-xs font-medium text-primary/70'>{service.category}</div>
                </div>
              </UnifiedCard>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </section>
  )
}
