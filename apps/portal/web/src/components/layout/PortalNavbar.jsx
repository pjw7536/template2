import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { ChevronDownIcon, MenuIcon } from "lucide-react"

import { GaNEtchLogo, ThemeColorSelector, ThemeToggle } from "@/components/common"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { useAuth } from "@/lib/auth"
import {
  hasAnyScopeAccess,
  hasEveryScopeAccess,
  hasScopeAccess,
  hasScopeRole,
} from "@/lib/access/scopeAccess"
import { PORTAL_BRAND_KEY, resolvePortalBrand } from "@/lib/config/portalBranding"
import { buildProfileImageUrl, resolveProfileAvatarId } from "@/lib/profileImage"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

import { PortalNavLink } from "./PortalNavLink"
import { PortalProfileDropdown } from "./PortalProfileDropdown"

const NAV_HIDE_DELAY_MS = 3000
const NAV_ICON_CLASS_NAME = "size-4"
const NAV_MENU_TRIGGER_CLASS_NAME = "gap-1.5"
const NAV_MENU_LINK_CLASS_NAME = "flex w-full items-center gap-2"

function canShowNavigationItem(item, user) {
  if (item?.adminScope && !hasScopeRole(user, item.adminScope)) return false
  if (item?.appScope && !hasScopeAccess(user, item.appScope)) return false
  if (item?.requiredAppScopes && !hasEveryScopeAccess(user, item.requiredAppScopes)) return false
  if (item?.anyAppScopes && !hasAnyScopeAccess(user, item.anyAppScopes)) return false
  return true
}

function getVisibleNavigationItem(item, user) {
  if (!canShowNavigationItem(item, user)) return null
  if (!Array.isArray(item.children)) return item
  return {
    ...item,
    children: item.children
      .map((child) => getVisibleNavigationItem(child, user))
      .filter(Boolean),
  }
}

export function PortalNavbar({ navigationItems }) {
  const { user } = useAuth()
  const { theme = "system", systemTheme } = useTheme()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const isHomeRoute = pathname === "/"
  const shouldFadeNavItems = !isHomeRoute
  const hideTimerRef = useRef(null)
  const [isNavVisible, setIsNavVisible] = useState(() => pathname === "/")
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [openDesktopMenu, setOpenDesktopMenu] = useState(null)

  useEffect(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }

    if (!shouldFadeNavItems) {
      setIsNavVisible(true)
      return
    }

    setIsNavVisible(false)
  }, [shouldFadeNavItems])

  useEffect(() => {
    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current)
        hideTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    setIsMobileMenuOpen(false)
    setOpenDesktopMenu(null)
  }, [pathname])

  useEffect(() => {
    const desktopMediaQuery = window.matchMedia("(min-width: 768px)")
    const closeMenuOnDesktop = (event) => {
      if (event.matches) {
        setIsMobileMenuOpen(false)
      }
    }

    desktopMediaQuery.addEventListener("change", closeMenuOnDesktop)
    return () => {
      desktopMediaQuery.removeEventListener("change", closeMenuOnDesktop)
    }
  }, [])

  const showNavItems = () => {
    if (!shouldFadeNavItems) return
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }
    setIsNavVisible(true)
  }

  const scheduleHideNavItems = () => {
    if (!shouldFadeNavItems) return
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
    }
    hideTimerRef.current = setTimeout(() => {
      setIsNavVisible(false)
      hideTimerRef.current = null
    }, NAV_HIDE_DELAY_MS)
  }

  const handleBlur = (event) => {
    if (event.currentTarget.contains(event.relatedTarget)) {
      return
    }
    scheduleHideNavItems()
  }

  const navItemVisibilityClassName = shouldFadeNavItems
    ? cn(
      "transition-opacity duration-700",
      isNavVisible ? "opacity-100" : "opacity-0 pointer-events-none",
    )
    : ""
  const profileAvatarId = resolveProfileAvatarId(user)
  const avatarSrc = buildProfileImageUrl(profileAvatarId)
  const displayName = user?.username || user?.email || "U"
  const initials = displayName.slice(0, 1).toUpperCase()

  const renderIcon = (Icon) => {
    if (!Icon) return null
    return <Icon className={NAV_ICON_CLASS_NAME} />
  }

  const closeDesktopMenu = () => {
    setOpenDesktopMenu(null)
  }

  const navigateDesktopParentItem = (item) => {
    closeDesktopMenu()
    if (item.external) {
      window.open(item.href, "_blank", "noopener,noreferrer")
      return
    }
    navigate(item.href)
  }

  const handleDesktopParentItemClick = (event, item) => {
    if (!item.href) return
    event.preventDefault()
    navigateDesktopParentItem(item)
  }

  const handleDesktopParentItemKeyDown = (event, item) => {
    if (!item.href || !["Enter", " "].includes(event.key)) return
    event.preventDefault()
    navigateDesktopParentItem(item)
  }

  const renderNavigationLink = (item) => {
    if (item.external) {
      return (
        <a
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          className={NAV_MENU_LINK_CLASS_NAME}
          onClick={closeDesktopMenu}
        >
          {renderIcon(item.icon)}
          {item.title}
        </a>
      )
    }

    return (
      <PortalNavLink
        href={item.href}
        className={NAV_MENU_LINK_CLASS_NAME}
        onNavigate={closeDesktopMenu}
      >
        {renderIcon(item.icon)}
        {item.title}
      </PortalNavLink>
    )
  }

  const renderSubNavigationItem = (item) => {
    const hasChildren = Array.isArray(item.children) && item.children.length > 0

    if (!hasChildren) {
      return (
        <DropdownMenuItem key={item.title} asChild>
          {renderNavigationLink(item)}
        </DropdownMenuItem>
      )
    }

    return (
      <DropdownMenuSub key={item.title}>
        <DropdownMenuSubTrigger
          className={item.href ? "cursor-pointer" : undefined}
          onClick={(event) => handleDesktopParentItemClick(event, item)}
          onKeyDown={(event) => handleDesktopParentItemKeyDown(event, item)}
        >
          {renderIcon(item.icon)}
          {item.title}
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="w-36">
          {item.children.map((child) => (
            <DropdownMenuItem key={child.title} asChild>
              {renderNavigationLink(child)}
            </DropdownMenuItem>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    )
  }

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false)
  }

  const renderMobileNavigationLink = (item, nested = false) => (
    <Button
      key={item.title}
      asChild
      variant="ghost"
      size="sm"
      className={cn("w-full justify-start gap-2", nested && "pl-8")}
    >
      <PortalNavLink
        href={item.href}
        target={item.external ? "_blank" : undefined}
        rel={item.external ? "noopener noreferrer" : undefined}
        onNavigate={closeMobileMenu}
      >
        {renderIcon(item.icon)}
        {item.title}
      </PortalNavLink>
    </Button>
  )

  const renderMobileSubNavigationItem = (item) => {
    const hasChildren = Array.isArray(item.children) && item.children.length > 0

    if (!hasChildren) {
      return renderMobileNavigationLink(item, true)
    }

    const trigger = (
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size={item.href ? "icon" : "sm"}
          className={cn(
            item.href ? "size-8 shrink-0" : "w-full justify-start gap-2 pl-8",
          )}
          aria-label={item.href ? `${item.title} 하위 메뉴 펼치기` : undefined}
        >
          {!item.href ? renderIcon(item.icon) : null}
          {!item.href ? item.title : null}
          <ChevronDownIcon
            className={cn(
              "size-3.5 transition-transform group-data-[state=open]/mobile-sub:rotate-180",
              !item.href && "ml-auto",
            )}
            aria-hidden="true"
          />
        </Button>
      </CollapsibleTrigger>
    )

    return (
      <Collapsible key={item.title} className="group/mobile-sub">
        {item.href ? (
          <div className="flex items-center gap-1 pr-2">
            <div className="min-w-0 flex-1">
              {renderMobileNavigationLink(item, true)}
            </div>
            {trigger}
          </div>
        ) : trigger}
        <CollapsibleContent className="space-y-1 pt-1">
          {item.children.map((child) => renderMobileNavigationLink(child, true))}
        </CollapsibleContent>
      </Collapsible>
    )
  }

  const visibleNavigationItems = navigationItems
    .map((navItem) => ({
      ...navItem,
      items: navItem.items
        ?.map((item) => getVisibleNavigationItem(item, user))
        .filter(Boolean),
    }))
    .filter((navItem) => canShowNavigationItem(navItem, user))
    .filter((navItem) => navItem.href || (Array.isArray(navItem.items) && navItem.items.length > 0))
  const brand = resolvePortalBrand(pathname)
  const brandMark = brand.mark
  const BrandIcon = brandMark?.type === "icon" ? brandMark.icon : null
  const resolvedTheme = theme === "system" ? systemTheme : theme
  const brandImageSrc =
    brandMark?.type === "image" && resolvedTheme === "dark" && brandMark.darkSrc
      ? brandMark.darkSrc
      : brandMark?.src
  const shouldUsePortalLogo = brand.key === PORTAL_BRAND_KEY

  return (
    <div
      className="flex h-full w-full items-center gap-2 px-3 sm:gap-4 sm:px-4 md:gap-6 md:px-6"
      onMouseEnter={showNavItems}
      onMouseLeave={scheduleHideNavItems}
      onFocusCapture={showNavItems}
      onBlurCapture={handleBlur}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2 md:flex-none md:gap-4 lg:flex-1">
        <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
          <SheetTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 md:hidden"
              aria-label="메뉴 열기"
            >
              <MenuIcon className="size-5" aria-hidden="true" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80 max-w-full gap-0 p-0">
            <SheetHeader className="border-b px-4 py-4 pr-14">
              <SheetTitle>{brand.name}</SheetTitle>
              <SheetDescription>이동할 메뉴를 선택하세요.</SheetDescription>
            </SheetHeader>
            <nav
              className="min-h-0 flex-1 overflow-y-auto p-3"
              aria-label="모바일 포털 내비게이션"
            >
              <div className="flex flex-col gap-1">
                {visibleNavigationItems.map((navItem) => {
                  const Icon = navItem.icon

                  if (navItem.href) {
                    return renderMobileNavigationLink(navItem)
                  }

                  return (
                    <Collapsible key={navItem.title} className="group/mobile-group">
                      <CollapsibleTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          className="w-full justify-start gap-2"
                        >
                          {renderIcon(Icon)}
                          {navItem.title}
                          <ChevronDownIcon
                            className="ml-auto size-3.5 transition-transform group-data-[state=open]/mobile-group:rotate-180"
                            aria-hidden="true"
                          />
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent className="space-y-1 pt-1">
                        {navItem.items?.map(renderMobileSubNavigationItem)}
                      </CollapsibleContent>
                    </Collapsible>
                  )
                })}
              </div>
            </nav>
            <SheetFooter className="border-t p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">화면 설정</span>
                <div className="flex items-center gap-1">
                  <ThemeToggle />
                  <ThemeColorSelector />
                </div>
              </div>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        <PortalNavLink href="/" className="flex min-w-0 items-center gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center">
            {shouldUsePortalLogo ? (
              <GaNEtchLogo className="react-logo-circles--navbar" compact decorative />
            ) : null}
            {!shouldUsePortalLogo && brandMark?.type === "image" ? (
              <img
                src={brandImageSrc}
                alt={brandMark.alt ?? brand.name}
                className="size-8 object-contain"
              />
            ) : null}
            {!shouldUsePortalLogo && BrandIcon ? <BrandIcon className="size-4" aria-hidden="true" /> : null}
          </span>
          <span className="max-w-32 truncate text-base font-semibold sm:max-w-none md:text-xl">
            {brand.name}
          </span>
        </PortalNavLink>
      </div>

      <nav
        className="hidden min-w-0 flex-1 justify-center md:flex"
        aria-label="Portal navigation"
      >
        <div className="flex items-center justify-center gap-1">
          {visibleNavigationItems.map((navItem) => {
            const Icon = navItem.icon
            if (navItem.href) {
              return (
                <Button
                  key={navItem.title}
                  asChild
                  variant="ghost"
                  className={navItemVisibilityClassName}
                >
                  <PortalNavLink href={navItem.href}>
                    {renderIcon(Icon)}
                    {navItem.title}
                  </PortalNavLink>
                </Button>
              )
            }

            return (
              <DropdownMenu
                key={navItem.title}
                modal={false}
                open={openDesktopMenu === navItem.title}
                onOpenChange={(open) => setOpenDesktopMenu(open ? navItem.title : null)}
              >
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    className={cn(
                      NAV_MENU_TRIGGER_CLASS_NAME,
                      navItemVisibilityClassName,
                    )}
                  >
                    {renderIcon(Icon)}
                    {navItem.title}
                    <ChevronDownIcon className="size-3" aria-hidden="true" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-38">
                  <DropdownMenuGroup>
                    {navItem.items?.map(renderSubNavigationItem)}
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            )
          })}
        </div>
      </nav>

      <div className="flex shrink-0 items-center justify-end gap-1 sm:gap-2 md:flex-none md:gap-4 lg:flex-1">
        <ThemeToggle className="hidden md:inline-flex" />
        <ThemeColorSelector className="hidden md:inline-flex" />
        <PortalProfileDropdown
          trigger={
            <Button variant="ghost" className="h-full p-0">
              <Avatar className="size-9.5 rounded-full">
                <AvatarImage src={avatarSrc || undefined} alt={displayName} />
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
            </Button>
          }
        />
      </div>
    </div>
  )
}
