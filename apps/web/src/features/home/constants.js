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
      { title: 'ESOP Dashboard', href: '/esop_dashboard' },
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
      { title: 'VOC', href: '/voc' },
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
    alt: 'Lila Gomez',
    name: 'Lila Gomez',
    role: 'Product Marketing Lead',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-7.png',
    alt: 'Samuel Wright',
    name: 'Samuel Wright',
    role: 'Customer Success Lead',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-8.png',
    alt: 'Priya Nair',
    name: 'Priya Nair',
    role: 'Data Scientist',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-9.png',
    alt: 'Ethan Moore',
    name: 'Ethan Moore',
    role: 'Solutions Architect',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-10.png',
    alt: 'Hana Suzuki',
    name: 'Hana Suzuki',
    role: 'Backend Engineer',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-11.png',
    alt: 'Marco Silva',
    name: 'Marco Silva',
    role: 'Mobile Engineer',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-12.png',
    alt: 'Ava Bennett',
    name: 'Ava Bennett',
    role: 'People Operations Manager',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-13.png',
    alt: 'Nora Park',
    name: 'Nora Park',
    role: 'Product Operations',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-14.png',
    alt: 'Felix Lange',
    name: 'Felix Lange',
    role: 'Security Engineer',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-15.png',
    alt: 'Sara Idris',
    name: 'Sara Idris',
    role: 'QA Lead',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-16.png',
    alt: 'Leo Martin',
    name: 'Leo Martin',
    role: 'Growth Strategist',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-17.png',
    alt: 'Bianca Russo',
    name: 'Bianca Russo',
    role: 'Creative Director',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-18.png',
    alt: 'Omar Farouk',
    name: 'Omar Farouk',
    role: 'Platform Engineer',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-19.png',
    alt: 'Chloe Nguyen',
    name: 'Chloe Nguyen',
    role: 'Design Technologist',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-20.png',
    alt: 'Daniel Rivera',
    name: 'Daniel Rivera',
    role: 'Finance Lead',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-21.png',
    alt: 'Jisoo Han',
    name: 'Jisoo Han',
    role: 'Chief of Staff',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
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
