import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  UserIcon,
  SettingsIcon,
  UsersIcon,
  LogOutIcon
} from 'lucide-react'

import { useAuth } from '@/lib/auth'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'

const ProfileDropdown = ({
  trigger,
  defaultOpen,
  align = 'end'
}) => {
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const displayName = user?.name || 'John Doe'
  const email = user?.email || 'john.doe@example.com'
  const avatar =
    user?.avatar ||
    user?.photoUrl ||
    'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-1.png'
  const initials = (displayName || email || 'JD').slice(0, 2).toUpperCase()

  const handleLogout = useCallback(() => {
    logout()
      .catch(() => { })
      .finally(() => {
        navigate('/login')
      })
  }, [logout, navigate])

  const handleMyAccount = useCallback(() => {
    navigate('/account')
  }, [navigate])

  return (
    <DropdownMenu defaultOpen={defaultOpen}>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent className='w-80' align={align || 'end'}>
        <DropdownMenuLabel className='flex items-center gap-4 px-4 py-2.5 font-normal'>
          <div className='relative'>
            <Avatar className='size-10'>
              <AvatarImage
                src={avatar}
                alt={displayName} />
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <span
              className='ring-card absolute right-0 bottom-0 block size-2 rounded-full bg-green-600 ring-2' />
          </div>
          <div className='flex flex-1 flex-col items-start'>
            <span className='text-foreground text-lg font-semibold'>{displayName}</span>
            <span className='text-muted-foreground text-base'>{email}</span>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem
            className='px-4 py-2.5 text-base'
            onSelect={(event) => {
              event.preventDefault()
              handleMyAccount()
            }}>
            <UserIcon className='text-foreground size-5' />
            <span>My account</span>
          </DropdownMenuItem>
          <DropdownMenuItem className='px-4 py-2.5 text-base'>
            <SettingsIcon className='text-foreground size-5' />
            <span>Settings</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem className='px-4 py-2.5 text-base'>
            <UsersIcon className='text-foreground size-5' />
            <span>Manage team</span>
          </DropdownMenuItem>

        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          variant='destructive'
          className='px-4 py-2.5 text-base'
          onSelect={handleLogout}>
          <LogOutIcon className='size-5' />
          <span>Logout</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default ProfileDropdown
