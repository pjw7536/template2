import {
  BookOpenIcon,
  LayoutGridIcon,
  MessageSquareIcon
} from 'lucide-react'

export const navigationItems = [
  {
    title: 'Apps',
    icon: LayoutGridIcon,
    items: [
      { title: 'ESOP Dashboard', href: '/landing/esop-dashboard' },
      { title: 'Timeline(개발중)', href: '/timeline' },
      { title: 'Appstore(개발중)', href: '/appstore' },
    ]
  },
  {
    title: 'About Us',
    icon: BookOpenIcon,
    items: [
      { title: 'Team', href: '#' }
    ]
  },
  {
    title: 'Contacts',
    icon: MessageSquareIcon,
    items: [
      { title: 'Q&A', href: '/landing/qna' },
      { title: 'Etch Confluence', href: '#' },

    ]
  }
]


export const teamMembers = [
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-1.png',
    alt: 'Phillip Rothman',
    name: 'Phillip Rothman',
    role: 'Founder & CEO',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-2.png',
    alt: 'James Kenter',
    name: 'James Kenter',
    role: 'Engineering Manager',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-3.png',
    alt: 'Alena Lubin',
    name: 'Alena Lubin',
    role: 'Frontend Developer',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-4.png',
    alt: 'Cristofer Kenter',
    name: 'Cristofer Kenter',
    role: 'Product Designer',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-5.png',
    alt: 'Minji Choi',
    name: 'Minji Choi',
    role: 'Data Strategist',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-6.png',
    alt: 'Ethan Moore',
    name: 'Ethan Moore',
    role: 'Solutions Architect',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  }
]

export const marqueeApps = [
  {
    name: 'Ola',
    description: 'Ola Tech reshapes our access to information.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/ola-icon.png'
  },
  {
    name: 'Apple',
    description: 'Apple has transformed our tech connections.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/apple-icon.png'
  },
  {
    name: 'Notion',
    description: 'Google changed how we find information.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/notion-white.png'
  },
  {
    name: 'Meta',
    description: 'Meta changed how we connect.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/meta-icon.png'
  },
  {
    name: 'Zoom',
    description: 'Zoom changed how we connect.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/camera-icon.png'
  },
  {
    name: 'Framer',
    description: 'Framer revolutionized our data collection.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/framer-logo.png'
  },
  {
    name: 'Slack',
    description: 'Team collaboration tool.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/slack-icon.png'
  },
  {
    name: 'Github',
    description: 'GitHub enhances collaboration.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/github-white.png'
  },
  {
    name: 'Discord',
    description: 'Discord transforms our connections.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/discord-icon.png'
  },
  {
    name: 'Figma',
    description: 'Figma transformed our connections.',
    image: 'https://cdn.shadcnstudio.com/ss-assets/brand-logo/figma-icon.png'
  }
]
