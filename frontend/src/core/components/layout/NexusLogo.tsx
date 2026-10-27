import React from "react";

interface NexusLogoProps {
  size?: number;
}

/** Nexus logo mark — ascending bar-chart with circuit nodes */
export const NexusLogo: React.FC<NexusLogoProps> = ({ size = 32 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="Nexus"
  >
    <defs>
      <linearGradient id="nexus-bar-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#00e676" />
      </linearGradient>
      <linearGradient id="nexus-line-grad" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#00e676" />
      </linearGradient>
    </defs>

    {/* Bar 1 — left, short */}
    <rect x="3" y="20" width="5" height="9" rx="1.5" fill="url(#nexus-bar-grad)" opacity="0.7" />

    {/* Bar 2 — center, medium */}
    <rect x="11" y="14" width="5" height="15" rx="1.5" fill="url(#nexus-bar-grad)" opacity="0.85" />

    {/* Bar 3 — right, tall */}
    <rect x="19" y="6" width="5" height="23" rx="1.5" fill="url(#nexus-bar-grad)" />

    {/* Connector line across bar tops */}
    <line x1="5.5" y1="19.5" x2="21.5" y2="5.5"
      stroke="url(#nexus-line-grad)" strokeWidth="1.5" strokeLinecap="round" />

    {/* Node dots on bar tops */}
    <circle cx="5.5" cy="19.5" r="2" fill="#3b82f6" />
    <circle cx="13.5" cy="13.5" r="2" fill="#1ca8ff" />
    <circle cx="21.5" cy="5.5" r="2.2" fill="#00e676" />

    {/* Pulse ring on top node */}
    <circle cx="21.5" cy="5.5" r="4" stroke="#00e676" strokeWidth="1"
      strokeOpacity="0.35" fill="none" />
  </svg>
);
