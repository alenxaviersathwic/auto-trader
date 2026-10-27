import React from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useMenuItems } from "../../navigation/menuRegistry";
import { Cpu } from "lucide-react";
import { NexusLogo } from "./NexusLogo";

export const SideMenu: React.FC = () => {
  const menuItems = useMenuItems();
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo-container">
          <NexusLogo size={28} />
        </div>
        <div className="brand-text">
          <span className="brand-title">NEXUS</span>
          <span className="brand-subtitle">ALGO TERMINAL</span>
        </div>
      </div>

      <div className="sidebar-section-title">NAVIGATION</div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => {
          const Icon = item.icon || Cpu;
          const isActive = currentPath.startsWith(item.path);

          return (
            <Link
              key={item.id}
              to={item.path}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              <Icon size={18} className="nav-icon" />
              <span className="nav-label">{item.label}</span>
              {item.badge && <span className="nav-badge">{item.badge}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="engine-status-card">
          <div className="status-indicator-dot online"></div>
          <div className="status-card-text">
            <span className="status-title">FastAPI Core</span>
            <span className="status-meta">1 Worker • Asia/Kolkata</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
