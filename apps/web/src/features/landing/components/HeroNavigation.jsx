import { useEffect, useState } from 'react';

import { useMedia } from 'react-use'
import { ChevronRightIcon, CircleSmallIcon, MenuIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle
} from '@/components/ui/navigation-menu'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger
} from '@/components/ui/sheet'
import Logo from '@/features/landing/components/Logo'

import { cn } from '@/lib/utils'

const ListItem = (props) => {
  const { title, href, icon: Icon, badge, description, splitItems } = props

  return (
    <li className={cn({ 'h-19.5': description && splitItems })}>
      <NavigationMenuLink href={href} className={cn({ 'flex flex-row items-start gap-2': icon })}>
        {Icon && (
          <span
            className='bg-popover [&>svg]:text-popover-foreground! flex aspect-square size-7 shrink-0 items-center justify-center rounded-sm border [&>svg]:size-4'>
            <Icon className='size-4' />
          </span>
        )}
        {description ? (
          <div className='space-y-0.5'>
            <div className={cn('font-medium', { 'flex items-center gap-1.5': badge })}>
              {title}
              {badge}
            </div>
            <p className='text-muted-foreground line-clamp-2'>{description}</p>
          </div>
        ) : (
          <div className={cn('font-medium', { 'flex items-center gap-1.5': badge })}>
            {title}
            {badge}
          </div>
        )}
      </NavigationMenuLink>
    </li>
  );
}

const HeroNavigation = ({
  navigationItems,
  navigationClassName
}) => {
  return (
    <NavigationMenu viewport={false} className={cn('hidden lg:block', navigationClassName)}>
      <NavigationMenuList className='flex-wrap gap-0'>
        {navigationItems.map(navItem => {
          const Icon = navItem.icon
          if (navItem.href) {
            // Root link item
            return (
              <NavigationMenuItem key={navItem.title}>
                <NavigationMenuLink
                  href={navItem.href}
                  className={cn(
                    navigationMenuTriggerStyle(),
                    'text-muted-foreground px-3 py-1.5 text-base'
                  )}>
                  <span className='flex items-center gap-1.5'>
                    {Icon && <Icon className='size-4' />}
                    {navItem.title}
                  </span>
                </NavigationMenuLink>
              </NavigationMenuItem>
            );
          }

          // Section with dropdown
          return (
            <NavigationMenuItem key={navItem.title}>
              <NavigationMenuTrigger className='text-muted-foreground px-3 py-1.5 text-base [&_svg]:size-4'>
                <span className='flex items-center gap-1.5'>
                  {Icon && <Icon className='size-4' />}
                  {navItem.title}
                </span>
              </NavigationMenuTrigger>
              <NavigationMenuContent className='absolute left-1/2 w-auto -translate-x-1/2 shadow-lg!'>
                {navItem.splitItems ? (
                  <div className={cn('grid grid-cols-1 gap-2', navItem.contentClassName)}>
                    {navItem.items.map(section => (
                      <div key={section.title} className='grid grid-cols-1 gap-2'>
                        <div className='text-muted-foreground px-2 text-sm'>{section.title}</div>
                        <ul
                          className={cn('grid grid-cols-1 gap-0.5', {
                            'gap-2': section.items.find(item => item.description)
                          })}>
                          {section.items.map((item, index) => (
                            <ListItem
                              key={index}
                              icon={item.icon}
                              title={item.title}
                              description={item.description}
                              href={item.href}
                              badge={item.badge}
                              splitItems={navItem.splitItems} />
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                ) : (
                  <ul
                    className={cn(
                      'grid grid-cols-1 gap-0.5',
                      { 'gap-2': navItem.items?.find(item => item.description) },
                      navItem.contentClassName
                    )}>
                    {navItem.items?.map((item, index) => (
                      <ListItem
                        key={index}
                        icon={item.icon}
                        title={item.title}
                        description={item.description}
                        href={item.href}
                        badge={item.badge} />
                    ))}
                  </ul>
                )}
              </NavigationMenuContent>
            </NavigationMenuItem>
          );
        })}
      </NavigationMenuList>
    </NavigationMenu>
  );
}

const HeroNavigationMobile = ({
  navigationItems,
  triggerClassName,
  screenSize = 1023
}) => {
  const [open, setOpen] = useState(false)
  const isMobile = useMedia(`(max-width: ${screenSize}px)`, false)

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
      <SheetTrigger asChild>
        <Button
          variant='outline'
          size='icon'
          className={cn('inline-flex lg:hidden', triggerClassName)}>
          <MenuIcon />
          <span className='sr-only'>Menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side='left' className='w-75 gap-0 p-0'>
        <SheetHeader className='p-4'>
          <SheetTitle hidden />
          <SheetDescription hidden />
          <a href='#' onClick={handleLinkClick} className='self-start'>
            <Logo className='gap-3' />
          </a>
        </SheetHeader>
        <div className='space-y-0.5 overflow-y-auto p-2'>
          {navigationItems.map((navItem, index) => {
            const Icon = navItem.icon
            if (navItem.href) {
              return (
                <a
                  key={navItem.title}
                  href={navItem.href}
                  className='hover:bg-accent flex items-center gap-2 rounded-sm px-3 py-2 text-sm'
                  onClick={handleLinkClick}>
                  {Icon && <Icon className='size-4' />}
                  {navItem.title}
                </a>
              );
            }

            return (
              <Collapsible key={index} className='w-full'>
                <CollapsibleTrigger
                  className='hover:bg-accent group flex w-full items-center justify-between rounded-sm px-3 py-2 text-sm'>
                  <div className='flex items-center gap-2'>{navItem.title}</div>
                  <ChevronRightIcon
                    className='size-4 shrink-0 transition-transform duration-300 group-data-[state=open]:rotate-90' />
                </CollapsibleTrigger>
                <CollapsibleContent
                  className='data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden transition-all duration-300'>
                  {navItem.splitItems
                    ? navItem.items.map((item, i) => (
                      <div key={i} className='mt-1.5'>
                        <div className='text-muted-foreground mb-1 pl-4.5 text-xs font-medium'>{item.title}</div>
                        {item.items.map((subItem, j) => (
                          <a
                            key={j}
                            href={subItem.href}
                            className='hover:bg-accent ml-4.5 flex items-center gap-2 rounded-sm px-3 py-2 text-sm'
                            onClick={handleLinkClick}>
                            {subItem.icon ? subItem.icon : <CircleSmallIcon className='size-4' />}
                            {subItem.title}
                          </a>
                        ))}
                      </div>
                    ))
                    : navItem.items?.map(item => (
                      <a
                        key={item.title}
                        href={item.href}
                        className='hover:bg-accent ml-3 flex items-center gap-2 rounded-sm px-3 py-2 text-sm'
                        onClick={handleLinkClick}>
                        {item.icon ? <item.icon className='size-4' /> : <CircleSmallIcon className='size-4' />}
                        {item.title}
                      </a>
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

export { HeroNavigation, HeroNavigationMobile };
