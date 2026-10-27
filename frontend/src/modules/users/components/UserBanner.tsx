import React from "react";
import { User } from "../types/users.types";
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  RefreshCw,
} from "lucide-react";

interface UserBannerProps {
  defaultUser: User | null | undefined;
  isLoading: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const UserBanner: React.FC<UserBannerProps> = ({
  defaultUser,
  isLoading,
  onRefresh,
  isRefreshing,
}) => {
  if (isLoading) {
    return (
      <div className="user-banner skeleton">
        <div className="banner-loading-text">Loading default user state...</div>
      </div>
    );
  }

  if (!defaultUser) {
    return (
      <div className="user-banner banner-warning">
        <div className="banner-icon-box warn">
          <AlertTriangle size={20} />
        </div>
        <div className="banner-content">
          <h3 className="banner-title">No Default Market Data User</h3>
          <p className="banner-subtitle">
            An active default Upstox account is required to stream real-time quotes and execute automated orders.
            Create your first user or set an active account as default below.
          </p>
        </div>
      </div>
    );
  }

  const upstox = defaultUser.upstox;
  const authStatus = upstox?.authStatus || "NEVER";

  const renderStatusBadge = () => {
    switch (authStatus) {
      case "VALID":
        return (
          <span className="badge badge--green">
            <CheckCircle2 size={13} />
            <span>Token Valid</span>
          </span>
        );
      case "EXPIRED":
        return (
          <span className="badge badge--amber">
            <AlertTriangle size={13} />
            <span>Token Expired</span>
          </span>
        );
      case "AUTH_FAILED":
        return (
          <span className="badge badge--red">
            <XCircle size={13} />
            <span>Auth Failed</span>
          </span>
        );
      default:
        return (
          <span className="badge badge--slate">
            <Clock size={13} />
            <span>Never Authenticated</span>
          </span>
        );
    }
  };

  const formatExpiry = (iso: string | null | undefined) => {
    if (!iso) return "No expiration set";
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="user-banner banner-active">
      <div className="banner-left">
        <div className="banner-icon-box success">
          <ShieldCheck size={24} />
        </div>
        <div className="banner-info">
          <div className="banner-header-row">
            <span className="banner-tag">DEFAULT TRADING ACCOUNT</span>
            {renderStatusBadge()}
            {upstox?.autoAuthEnabled && (
              <span className="badge badge--cyan">
                <Zap size={11} />
                <span>Auto-Auth Enabled</span>
              </span>
            )}
          </div>
          <div className="banner-user-name">
            <h2>{defaultUser.name}</h2>
            {upstox?.upstoxUserId && (
              <span className="upstox-id">ID: {upstox.upstoxUserId}</span>
            )}
            {upstox?.profileName && (
              <span className="profile-name">({upstox.profileName})</span>
            )}
          </div>
          <div className="banner-meta-row">
            <span className="meta-item">
              <Clock size={13} />
              <span>Token Expires: {formatExpiry(upstox?.tokenExpiresAt)}</span>
            </span>
            {upstox?.lastAuthAt && (
              <span className="meta-item">
                <span>Last Auth: {formatExpiry(upstox.lastAuthAt)}</span>
              </span>
            )}
            {upstox?.lastError && (
              <span className="meta-item error-text">
                <XCircle size={13} />
                <span>Error: {upstox.lastError}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="banner-right">
        {onRefresh && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh default user status"
          >
            <RefreshCw size={14} className={isRefreshing ? "spin" : ""} />
            <span>{isRefreshing ? "Checking..." : "Refresh"}</span>
          </button>
        )}
      </div>
    </div>
  );
};
