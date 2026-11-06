import type { ReactNode } from "react";

export type IconName =
  | "home"
  | "building"
  | "layers"
  | "book"
  | "pulse"
  | "bell"
  | "calendar"
  | "refresh"
  | "chart"
  | "users";

export function Icon({ name }: { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" className="icon" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

const paths: Record<IconName, ReactNode> = {
  home: (
    <>
      <path d="M4 11 12 4l8 7" />
      <path d="M6 10.2V20h12v-9.8" />
      <path d="M10 20v-5h4v5" />
    </>
  ),
  building: (
    <>
      <path d="M4 20V6.5L12 3l8 3.5V20" />
      <path d="M9 20v-4h6v4" />
      <path d="M8 9h.01M12 9h.01M16 9h.01M8 13h.01M12 13h.01M16 13h.01" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 12 9 5 9-5" />
      <path d="m3 16 9 5 9-5" />
    </>
  ),
  book: (
    <>
      <path d="M5 4.5h9.5A3.5 3.5 0 0 1 18 8v12H8.5A3.5 3.5 0 0 0 5 16.5V4.5Z" />
      <path d="M5 16.5A3.5 3.5 0 0 1 8.5 13H18" />
    </>
  ),
  pulse: (
    <>
      <path d="M3 12h4l2.2-5 3.6 10 2.2-5H21" />
    </>
  ),
  bell: (
    <>
      <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2H4.5L6 16Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </>
  ),
  calendar: (
    <>
      <path d="M5 6h14v14H5z" />
      <path d="M8 4v4M16 4v4M5 10h14" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-2.2-5.5" />
      <path d="M20 4v5h-5" />
    </>
  ),
  chart: (
    <>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <path d="M8 16v-4" />
      <path d="M12 16V8" />
      <path d="M16 16v-6" />
    </>
  ),
  users: (
    <>
      <path d="M9 12a3.2 3.2 0 1 0-3.2-3.2A3.2 3.2 0 0 0 9 12Z" />
      <path d="M3.5 19.2a5.5 5.5 0 0 1 11 0" />
      <path d="M16 11.2a2.6 2.6 0 1 0-2.2-4" />
      <path d="M16.2 14.2a4.8 4.8 0 0 1 4.3 5" />
    </>
  ),
};

export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="3" fill="#8c2f2a" />
      <rect x="8" y="3" width="21" height="26" fill="#f3efe6" />
      <path d="M12 11h13M12 16h9M12 21h11" stroke="#1c1914" strokeWidth="1.6" />
      <circle cx="4" cy="9" r="1.15" fill="#f3efe6" />
      <circle cx="4" cy="16" r="1.15" fill="#f3efe6" />
      <circle cx="4" cy="23" r="1.15" fill="#f3efe6" />
    </svg>
  );
}
