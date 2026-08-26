import type { ReactNode } from 'react'
import type { IconName } from '../types'

interface IconProps {
  name: IconName
  size?: number
  className?: string
}

const ICONS: Record<IconName, ReactNode> = {
  book: (
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
  ),
  pen: (
    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z" />
    </>
  ),
  home: (
    <>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <path d="M9 22V12h6v10" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>
  ),
  star: (
    <path d="M11.53 2.3a.53.53 0 0 1 .94 0l2.9 5.88a.53.53 0 0 0 .4.29l6.5.94a.53.53 0 0 1 .3.9l-4.7 4.6a.53.53 0 0 0-.15.46l1.1 6.48a.53.53 0 0 1-.77.56l-5.8-3.05a.53.53 0 0 0-.5 0l-5.8 3.05a.53.53 0 0 1-.77-.56l1.1-6.48a.53.53 0 0 0-.15-.46l-4.7-4.6a.53.53 0 0 1 .3-.9l6.5-.94a.53.53 0 0 0 .4-.29l2.9-5.88z" />
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.35-4.35" />
    </>
  ),
  user: (
    <>
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </>
  ),
  menu: (
    <>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </>
  ),
  'chevron-down': <path d="m6 9 6 6 6-6" />,
  copy: (
    <>
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </>
  ),
  refresh: (
    <>
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </>
  ),
  'thumbs-up': (
    <>
      <path d="M7 10v12" />
      <path d="M15 5.88 13.67 9.2c-.36.74-.9 1.35-1.57 1.8H7v11h9.24a2 2 0 0 0 1.92-1.45l2.14-7.45A2 2 0 0 0 17.66 12H15" />
    </>
  ),
  'thumbs-down': (
    <>
      <path d="M17 14V2" />
      <path d="M9 18.12 10.33 14.8c.36-.74.9-1.35 1.57-1.8H17V2H7.76a2 2 0 0 0-1.92 1.45L3.7 10.9A2 2 0 0 0 6.34 14H9" />
    </>
  ),
  square: <rect x="5" y="5" width="14" height="14" rx="2" />,
  send: (
    <>
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22 11 13 2 9 22 2z" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </>
  ),
  x: (
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>
  ),
}

export default function Icon({ name, size = 20, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  )
}

