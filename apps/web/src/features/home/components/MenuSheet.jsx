import { useEffect, useState } from 'react'

import { useMedia } from 'react-use'
import { ChevronRightIcon, CircleSmallIcon } from 'lucide-react'

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger
} from '@/components/ui/sheet'

import LogoSvg from '@/assets/svg/logo'
import { HomeNavLink } from './HomeNavLink'

const MenuSheet = ({
  trigger,
  logoName,
  navigationItems
}) => {
  const [open, setOpen] = useState(false)
  const isMobile = useMedia('(max-width: 767px)', false)

  const handleLinkClick = () => {
    setOpen(false)
  }

  useEffect(() => {
    if (!isMobile) {
      setOpen(false)
    }
  }, [isMobile])

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{trigger}</SheetTrigger>
      <SheetContent side='left' className='w-75 gap-0 p-0'>
        <SheetHeader className='p-4'>
          <SheetTitle hidden />
          <SheetDescription hidden />
          <HomeNavLink href='/' onNavigate={handleLinkClick} className='self-start'>
            <div className='flex items-center'>
              <LogoSvg className='size-8.5' />
              <span className='ml-2.5 text-xl font-semibold'>{logoName}</span>
            </div>
          </HomeNavLink>
        </SheetHeader>
        <div className='overflow-y-auto py-2'>
          {navigationItems.map(navItem => {
            const Icon = navItem.icon
            if (navItem.href) {
              return (
                <HomeNavLink
                  key={navItem.title}
                  href={navItem.href}
                  className='hover:bg-accent flex items-center gap-2 px-4 py-2 text-sm'
                  onNavigate={handleLinkClick}>
                  {Icon && <Icon className='size-4' />}
                  {navItem.title}
                </HomeNavLink>
              );
            }

            return (
              <Collapsible key={navItem.title} className='w-full'>
                <CollapsibleTrigger
                  className='hover:bg-accent group flex w-full items-center justify-between px-4 py-2 text-sm'>
                  <div className='flex items-center gap-2'>
                    {navItem.icon}
                    {navItem.title}
                  </div>
                  <ChevronRightIcon
                    className='size-4 shrink-0 transition-transform duration-300 group-data-[state=open]:rotate-90' />
                </CollapsibleTrigger>
                <CollapsibleContent
                  className='data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden transition-all duration-300'>
                  {navItem.items?.map(item => (
                    <HomeNavLink
                      key={item.title}
                      href={item.href}
                      className='hover:bg-accent flex items-center gap-2 px-4 py-2 text-sm'
                      onNavigate={handleLinkClick}>
                      <CircleSmallIcon className='ml-2 size-4' />
                      {item.title}
                    </HomeNavLink>
                  ))}
                </CollapsibleContent>
              </Collapsible>
            );
          })}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default MenuSheet
