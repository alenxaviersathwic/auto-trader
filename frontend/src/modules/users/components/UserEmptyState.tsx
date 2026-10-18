import React from "react";
import { UserPlus, Shield, Activity, Sparkles } from "lucide-react";

interface UserEmptyStateProps {
  onAddUser: () => void;
}

export const UserEmptyState: React.FC<UserEmptyStateProps> = ({ onAddUser }) => {
  return (
    <div className="user-empty-state-card">
      <div className="empty-icon-halo">
        <Shield size={38} className="text-emerald" />
      </div>

      <h3 className="empty-title">Add your first Upstox user</h3>
      <p className="empty-description">
        Connect your Upstox trading account with API credentials, mobile PIN, and TOTP secret.
        The first user created automatically becomes the system <strong>Default Account</strong> for real-time market data.
      </p>

      <div className="empty-features-list">
        <div className="empty-feature-item">
          <Sparkles size={14} className="text-cyan" />
          <span>Automated headless daily TOTP authentication</span>
        </div>
        <div className="empty-feature-item">
          <Activity size={14} className="text-emerald" />
          <span>Real-time market depth and quotes telemetry</span>
        </div>
        <div className="empty-feature-item">
          <Shield size={14} className="text-amber" />
          <span>Zero plaintext secrets (AES-GCM encrypted)</span>
        </div>
      </div>

      <button
        type="button"
        className="btn btn-primary btn-lg"
        onClick={onAddUser}
      >
        <UserPlus size={18} />
        <span>+ Add Upstox User</span>
      </button>
    </div>
  );
};
