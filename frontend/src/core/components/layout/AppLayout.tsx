import React from "react";
import { Outlet } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { SideMenu } from "./SideMenu";
import { httpClient } from "../../api/httpClient";
import {
  Database,
  Clock,
  ShieldCheck,
  Server,
  Layers,
} from "lucide-react";

interface HealthData {
  status: string;
  environment: string;
  timestamp: string;
  timezone: string;
  database: {
    connected: boolean;
    pgvector: boolean;
  };
}

export const AppLayout: React.FC = () => {
  // Real-time backend system health query
  const { data: health, isSuccess } = useQuery<HealthData>({
    queryKey: ["system", "health"],
    queryFn: () => httpClient.get("/health"),
    refetchInterval: 15000, // Refresh health status every 15s
  });

  const isDbUp = health?.database?.connected ?? false;
  const isVectorUp = health?.database?.pgvector ?? false;

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <SideMenu />

      {/* Main Execution Viewport */}
      <div className="app-main-viewport">
        {/* Top bar with real-time trading system telemetry */}
        <header className="app-topbar">
          <div className="topbar-left">
            <div className="terminal-badge">
              <Layers size={14} />
              <span>CORE ARCHITECTURE</span>
            </div>
            <span className="topbar-divider">/</span>
            <span className="topbar-context">High-Frequency Automated Engine</span>
          </div>

          <div className="topbar-right">
            {/* System Status Chips */}
            <div className={`status-chip ${isSuccess ? "chip-ok" : "chip-warn"}`}>
              <Server size={13} />
              <span>API: {health?.status || "Connecting..."}</span>
            </div>

            <div className={`status-chip ${isDbUp ? "chip-ok" : "chip-err"}`}>
              <Database size={13} />
              <span>PostgreSQL {isVectorUp ? "+ pgvector" : ""}</span>
            </div>

            <div className="status-chip chip-neutral">
              <Clock size={13} />
              <span>{health?.timezone || "Asia/Kolkata"}</span>
            </div>

            <div className="status-chip chip-accent">
              <ShieldCheck size={13} />
              <span>AES-GCM Active</span>
            </div>
          </div>
        </header>

        {/* Content Viewport */}
        <main className="app-content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
