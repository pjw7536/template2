import { useRef } from 'react'
import {
  BotMessageSquareIcon,
  CodeXmlIcon,
  DatabaseIcon,
  ChartSpline,
  Cloud,
  Cpu,
  Puzzle,
  Flame,
  HeartHandshake,
} from 'lucide-react'


import { Badge } from '@/components/ui/badge'

import { AnimatedBeam } from '@/components/ui/animated-beam'
import LogoVector from '@/assets/svg/logo-vector'

const HeroSection = () => {
  const containerRef = useRef(null)
  const iconRef1 = useRef(null)
  const iconRef2 = useRef(null)
  const iconRef3 = useRef(null)
  const iconRef4 = useRef(null)
  const iconRef5 = useRef(null)
  const iconRef6 = useRef(null)
  const iconRef7 = useRef(null)
  const spanRef1 = useRef(null)
  const spanRef2 = useRef(null)
  const spanRef3 = useRef(null)
  const spanRef4 = useRef(null)
  const spanRef5 = useRef(null)
  const spanRef6 = useRef(null)
  const spanRef7 = useRef(null)
  const spanRef8 = useRef(null)

  return (
    <section className='flex-1 overflow-hidden py-12 sm:py-8 lg:py-8'>
      <div
        className='mx-auto flex max-w-7xl flex-col items-center gap-8 px-4 sm:gap-16 sm:px-6 lg:gap-18 lg:px-8'>
        {/* Hero Content */}
        <div className='flex flex-col items-center gap-4 text-center'>
          <Badge variant='outline' className='text-sm font-normal'>
            Our Solution
          </Badge>

          <h1 className="text-2xl font-semibold sm:text-3xl lg:text-5xl lg:font-bold">
            <span className="shimmer-text">Connect</span> Your Data &{" "}
            <span className="shimmer-text">Boost</span> Productivity
          </h1>


          <p className='text-muted-foreground max-w-4xl text-xl'>
            흩어져 있던 데이터를 하나로 연결하고, 반복적인 업무를 자동화해 AI로 업무 부담을 줄여보세요.{' '}
            <br className='max-lg:hidden' /> 더 적은 노력으로 더 빠르고 스마트한 Workflow을 만들어드립니다.
          </p>

        </div>
        <div ref={containerRef} className='relative flex w-full flex-col items-center'>
          <div
            className='flex w-full max-w-4xl items-center justify-between max-md:hidden'>
            <div className='flex items-center gap-30'>
              <div
                ref={iconRef1}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <CodeXmlIcon className='size-7 stroke-1 lg:size-10' />
              </div>
              <span ref={spanRef1} className='size-0.5 max-md:hidden'></span>
              <div className="flex flex-col items-center gap-4 text-xl font-semibold text-foreground">
                <div className="flex items-start justify-center gap-8 text-lg font-semibold">

                  {/* 사람존중 */}
                  <div className="flex flex-col items-center gap-1">
                    <HeartHandshake className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span>사람존중</span>
                  </div>

                  {/* 다름의인정 */}
                  <div className="flex flex-col items-center gap-1">
                    <Puzzle className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span>다름의인정</span>
                  </div>

                  {/* Again열정 */}
                  <div className="flex flex-col items-center gap-1">
                    <Flame className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span>Again열정</span>
                  </div>

                </div>
              </div>
            </div>
            <div className='flex items-center gap-30'>
              <span ref={spanRef2} className='size-0.5 max-md:hidden'></span>
              <div
                ref={iconRef2}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <BotMessageSquareIcon className='size-7 stroke-1 lg:size-8' />
              </div>
            </div>
          </div>
          <div className='flex w-full items-center justify-between py-2.5'>
            <div
              ref={iconRef3}
              className='bg-background relative z-10 flex size-15 shrink-0 items-center justify-center rounded-xl border-[1.5px] shadow-xl md:size-18 lg:size-23'>
              <DatabaseIcon className='size-8 stroke-1 md:size-10 lg:size-13' />
            </div>
            <div
              className='flex items-center justify-between md:w-full md:max-w-70 lg:max-w-100'>
              <div className='flex w-full max-w-20 justify-between max-md:hidden'>
                <span ref={spanRef3} className='size-0.5'></span>
                <span ref={spanRef4} className='size-0.5'></span>
              </div>
              <div
                ref={iconRef4}
                className='bg-background relative z-20 flex items-center justify-center rounded-xl border p-2'>
                <div
                  className='bg-secondary flex size-16 items-center justify-center rounded-xl border-[1.5px] shadow-xl md:size-23'>
                  <div
                    className='flex size-10 items-center justify-center rounded-xl bg-black md:size-16'>
                    <LogoVector className='size-10 text-white md:size-16' />
                  </div>
                </div>
              </div>
              <div className='flex w-full max-w-20 justify-between max-md:hidden'>
                <span ref={spanRef5} className='size-0.5'></span>
                <span ref={spanRef6} className='size-0.5'></span>
              </div>
            </div>
            <div
              ref={iconRef5}
              className='bg-background relative z-10 flex size-15 shrink-0 items-center justify-center rounded-xl border-[1.5px] shadow-xl md:size-18 lg:size-23'>
              <ChartSpline className='size-8 stroke-1 md:size-10 lg:size-13' />
            </div>
          </div>
          <div
            className='flex w-full max-w-4xl items-center justify-between max-md:hidden'>
            <div className='flex items-center gap-30'>
              <div
                ref={iconRef6}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <Cloud className='size-6 stroke-1 lg:size-8' />
              </div>
              <span ref={spanRef7} className='size-0.5 max-md:hidden'></span>
            </div>


            <div className='flex items-center gap-30'>
              <span ref={spanRef8} className='size-0.5 max-md:hidden'></span>
              <div
                ref={iconRef7}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <Cpu className='size-7 stroke-1 lg:size-11' />
              </div>
            </div>
          </div>

          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef1}
            toRef={spanRef1}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef1}
            toRef={spanRef3}
            gradientStartColor='var(--primary)'
            duration={4.5}
            curvature={-45}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef2}
            toRef={spanRef2}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef2}
            toRef={spanRef6}
            gradientStartColor='var(--primary)'
            duration={4.5}
            curvature={-45}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef6}
            toRef={spanRef7}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef7}
            toRef={spanRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            curvature={40}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef7}
            toRef={spanRef8}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef8}
            toRef={spanRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            curvature={40}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef3}
            toRef={spanRef3}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef3}
            toRef={spanRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef4}
            toRef={iconRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />

          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef4}
            toRef={spanRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef5}
            toRef={spanRef6}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={spanRef6}
            toRef={iconRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />

          {/* Smaller screen */}

          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef3}
            toRef={iconRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='md:hidden' />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={iconRef4}
            toRef={iconRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='md:hidden' />
        </div>
      </div>
    </section>
  );
}

export default HeroSection
