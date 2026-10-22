import React from "react";
import { MasterHealth } from "../types/master.types";
import { Cpu, Wifi, WifiOff } from "lucide-react";

interface Props {
  health?: MasterHealth;
  isLoading?: boolean;
}

export const MasterHealthBadge: React.FC<Props> = ({ health, isLoading }) => {
  if (isLoading) return <div className="health-badge health-badge--loading"><Cpu size={13} /> Checking…</div>;
  if (!health) return null;

  return (
    <div className={`health-badge ${health.llmHealthy ? "health-badge--ok" : "health-badge--err"}`}>
      {health.llmHealthy ? <Wifi size={13} /> : <WifiOff size={13} />}
      <span>{health.llmModel}</span>
      <span className="health-sep">·</span>
      <span>{health.totalTools} tools</span>
    </div>
  );
};
