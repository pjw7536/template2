import { BellIcon, MenuIcon, SearchIcon } from 'lucide-react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle
} from '@/components/ui/navigation-menu'

import { ThemeColorSelector, ThemeToggle } from '@/components/common'
import { cn } from '@/lib/utils'

import LogoSvg from '@/assets/svg/logo'
import NotificationDropdown from './NotificationDropdown'
import ProfileDropdown from './ProfileDropdown'
import MenuSheet from './MenuSheet'

const Navbar = ({
  navigationItems
}) => {
  const renderIcon = (Icon) => {
    if (!Icon) return null
    return <Icon className='size-4' />
  }

  return (
    <header className='bg-background sticky top-0 z-50 border-b'>
      <div className='border-b'>
        <div
          className='mx-auto flex max-w-7xl items-center justify-between gap-8 px-4 py-3 sm:px-6'>
          <div className='flex items-center gap-4'>
            <MenuSheet
              logoName='Job Management'
              navigationItems={navigationItems}
              trigger={
                <Button variant='outline' size='icon' className='inline-flex lg:hidden'>
                  <MenuIcon />
                  <span className='sr-only'>Menu</span>
                </Button>
              } />
            <a href='#'>
              <div className='flex items-center'>
                <LogoSvg className='size-8' />
                <span className='ml-3 hidden text-xl font-semibold sm:block'>Etch기술팀</span>
              </div>
            </a>
          </div>
          <div
            className='mx-auto flex max-w-7xl items-center justify-between gap-8 px-4 py-1.5 sm:px-6'>
            <NavigationMenu viewport={false} className='hidden lg:block'>
              <NavigationMenuList className='flex-wrap justify-start'>
                {navigationItems.map(navItem => {
                  const Icon = navItem.icon
                  if (navItem.href) {
                    // Root link item
                    return (
                      <NavigationMenuItem key={navItem.title}>
                        <NavigationMenuLink
                          href={navItem.href}
                          className={cn(navigationMenuTriggerStyle(), 'flex flex-row items-center gap-1.5')}>
                          {renderIcon(Icon)}
                          {navItem.title}
                        </NavigationMenuLink>
                      </NavigationMenuItem>
                    );
                  }

                  // Section with dropdown
                  return (
                    <NavigationMenuItem key={navItem.title}>
                      <NavigationMenuTrigger className='gap-1.5'>
                        {renderIcon(Icon)}
                        {navItem.title}
                      </NavigationMenuTrigger>
                      <NavigationMenuContent
                        className='data-[motion=from-start]:slide-in-from-left-30! data-[motion=to-start]:slide-out-to-left-30! data-[motion=from-end]:slide-in-from-right-30! data-[motion=to-end]:slide-out-to-right-30! absolute w-auto'>
                        <ul className='grid w-38 gap-4'>
                          <li>
                            {navItem.items?.map(item => (
                              <NavigationMenuLink key={item.title} href={item.href}>
                                {item.title}
                              </NavigationMenuLink>
                            ))}
                          </li>
                        </ul>
                      </NavigationMenuContent>
                    </NavigationMenuItem>
                  );
                })}
              </NavigationMenuList>
            </NavigationMenu>
          </div>
          <div className='flex items-center gap-1.5 md:gap-4'>
            <Button variant='ghost' size='icon' className='flex md:hidden'>
              <SearchIcon />
            </Button>

            <ThemeToggle />
            <ThemeColorSelector />
            <NotificationDropdown
              trigger={
                <Button variant='ghost' size='icon' className='relative'>
                  <BellIcon />
                  <span className='bg-destructive absolute top-2 right-2.5 size-2 rounded-full' />
                </Button>
              } />
            <ProfileDropdown
              trigger={
                <Button variant='ghost' className='h-full p-0'>
                  <Avatar className='size-9.5 rounded-md'>
                    <AvatarImage src='https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-1.png' />
                    <AvatarFallback>JD</AvatarFallback>
                  </Avatar>
                </Button>
              } />
          </div>
        </div>
      </div>

    </header>
  );
}

export default Navbar
