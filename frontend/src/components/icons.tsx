import type { ReactNode, SVGProps } from 'react'

function I({ children, ...p }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...p}
    >
      {children}
    </svg>
  )
}

export const Icon = {
  dashboard: () => (
    <I>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </I>
  ),
  loop: () => (
    <I>
      <path d="M17 2l4 4-4 4" />
      <path d="M3 11v-1a4 4 0 0 1 4-4h14" />
      <path d="M7 22l-4-4 4-4" />
      <path d="M21 13v1a4 4 0 0 1-4 4H3" />
    </I>
  ),
  file: () => (
    <I>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M8 13h8M8 17h5" />
    </I>
  ),
  template: () => (
    <I>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18M9 21V9" />
    </I>
  ),
  users: () => (
    <I>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </I>
  ),
  box: () => (
    <I>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <path d="M3.3 7 12 12l8.7-5M12 22V12" />
    </I>
  ),
  calendar: () => (
    <I>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </I>
  ),
  percent: () => (
    <I>
      <path d="M19 5 5 19" />
      <circle cx="6.5" cy="6.5" r="2.5" />
      <circle cx="17.5" cy="17.5" r="2.5" />
    </I>
  ),
  tag: () => (
    <I>
      <path d="M20.59 13.41 13.42 20.6a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
      <circle cx="7" cy="7" r="1.5" />
    </I>
  ),
  invoice: () => (
    <I>
      <path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .67V2l-1 .67L16 2l-3 2-3-2-3 2z" />
      <path d="M8 9h8M8 13h6" />
    </I>
  ),
  card: () => (
    <I>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20M6 15h4" />
    </I>
  ),
  play: () => (
    <I>
      <circle cx="12" cy="12" r="10" />
      <path d="m10 8 6 4-6 4z" />
    </I>
  ),
  shield: () => (
    <I>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </I>
  ),
  logout: () => (
    <I>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </I>
  ),
  search: () => (
    <I>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </I>
  ),
  plus: () => (
    <I>
      <path d="M12 5v14M5 12h14" />
    </I>
  ),
  x: () => (
    <I>
      <path d="M18 6 6 18M6 6l12 12" />
    </I>
  ),
  trash: () => (
    <I>
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </I>
  ),
  edit: () => (
    <I>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" />
    </I>
  ),
  printer: () => (
    <I>
      <path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
    </I>
  ),
  send: () => (
    <I>
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
    </I>
  ),
  check: () => (
    <I>
      <path d="M20 6 9 17l-5-5" />
    </I>
  ),
  menu: () => (
    <I>
      <path d="M3 12h18M3 6h18M3 18h18" />
    </I>
  ),
  chevronLeft: () => (
    <I>
      <path d="m15 18-6-6 6-6" />
    </I>
  ),
  chevronRight: () => (
    <I>
      <path d="m9 18 6-6-6-6" />
    </I>
  ),
  alert: () => (
    <I>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </I>
  ),
  home: () => (
    <I>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <path d="M9 22V12h6v10" />
    </I>
  ),
}

export function BrandMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#714B67" />
      <circle cx="16" cy="16" r="8" fill="none" stroke="#fff" strokeWidth="3" />
      <circle cx="22" cy="10" r="3" fill="#2BC4CA" />
    </svg>
  )
}
