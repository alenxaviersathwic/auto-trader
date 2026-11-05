import React from "react";

interface OrderGridLogoProps {
  size?: number;
  className?: string;
}

/**
 * OrderGrid Brand Mark
 * Stylized high-frequency execution lattice with order nodes and grid matrix.
 */
export const OrderGridLogo: React.FC<OrderGridLogoProps> = ({ size = 28, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="OrderGrid"
  >
    <defs>
      <linearGradient id="ordergrid-bar-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stopColor="#387ed1" />
        <stop offset="100%" stopColor="#00d09c" />
      </linearGradient>
      <linearGradient id="ordergrid-glow" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#387ed1" />
        <stop offset="100%" stopColor="#00d09c" />
      </linearGradient>
    </defs>

    {/* Background Grid Frame */}
    <rect x="2" y="2" width="28" height="28" rx="6" fill="#0f172a" fillOpacity="0.8" stroke="#1e293b" strokeWidth="1" />

    {/* Order Depth Columns (Grid Lattice) */}
    <rect x="6" y="19" width="4.5" height="8" rx="1.5" fill="url(#ordergrid-bar-grad)" opacity="0.65" />
    <rect x="13.75" y="13" width="4.5" height="14" rx="1.5" fill="url(#ordergrid-bar-grad)" opacity="0.85" />
    <rect x="21.5" y="7" width="4.5" height="20" rx="1.5" fill="url(#ordergrid-bar-grad)" />

    {/* Order Routing Vector */}
    <line
      x1="8.25"
      y1="18.5"
      x2="23.75"
      y2="6.5"
      stroke="url(#ordergrid-glow)"
      strokeWidth="1.75"
      strokeLinecap="round"
    />

    {/* Execution Nodes */}
    <circle cx="8.25" cy="18.5" r="2" fill="#387ed1" />
    <circle cx="16" cy="12.5" r="2" fill="#38bdf8" />
    <circle cx="23.75" cy="6.5" r="2.2" fill="#00d09c" />

    {/* Target Trigger Pulse Ring */}
    <circle
      cx="23.75"
      cy="6.5"
      r="4"
      stroke="#00d09c"
      strokeWidth="1"
      strokeOpacity="0.4"
      fill="none"
    />
  </svg>
);

export const NexusLogo = OrderGridLogo;

