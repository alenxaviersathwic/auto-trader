import React, { useState, useEffect } from "react";
import { Outlet } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { SideMenu } from "./SideMenu";
import { httpClient } from "../../api/httpClient";
import { useDefaultUser } from "../../../modules/users/hooks/useUsers";
import {
  Clock,
  Layers,
  Activity,
  Bot,
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
  const [istTime, setIstTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setIstTime(
        now.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour12: true,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Real-time backend system health query
  const { data: health, isSuccess } = useQuery<HealthData>({
    queryKey: ["system", "health"],
    queryFn: () => httpClient.get("/health"),
    refetchInterval: 15000,
  });

  // Default trading user & token status telemetry
  const { data: defaultUser } = useDefaultUser();


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
              <span>AUTO-TRADER CORE</span>
            </div>
            <span className="topbar-divider">/</span>
            <span className="topbar-context">Algorithmic Trading Platform</span>
          </div>

          <div className="topbar-right">
            {/* Market Data Default User & Token Status Telemetry */}
            <div
              className={`status-chip ${
                defaultUser?.upstox?.authStatus === "VALID"
                  ? "chip-ok"
                  : defaultUser?.upstox?.authStatus === "EXPIRED"
                  ? "chip-warn"
                  : defaultUser?.upstox?.authStatus === "AUTH_FAILED"
                  ? "chip-err"
                  : "chip-neutral"
              }`}
            >
              <Activity size={13} />
              <span>
                Market data: <strong>{defaultUser?.name || "None"}</strong>
                {defaultUser?.upstox?.authStatus ? ` • ${defaultUser.upstox.authStatus}` : ""}
              </span>
            </div>

            {/* AI Engine Status Chip */}
            <div className={`status-chip ${isSuccess ? "chip-ok" : "chip-warn"}`}>
              <Bot size={13} />
              <span>AI Engine: {health?.status === "healthy" || isSuccess ? "ONLINE" : "CONNECTING"}</span>
            </div>

            <div className="status-chip chip-neutral font-mono">
              <Clock size={13} />
              <span>IST {istTime || "--:--:--"}</span>
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
