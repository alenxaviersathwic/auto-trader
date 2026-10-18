import React, { useState } from "react";
import { Copy, Check, ExternalLink, X, KeyRound } from "lucide-react";

interface RedirectUrlDialogProps {
  isOpen: boolean;
  redirectUri: string;
  userName?: string;
  onClose: () => void;
}

export const RedirectUrlDialog: React.FC<RedirectUrlDialogProps> = ({
  isOpen,
  redirectUri,
  userName,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(redirectUri);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      setCopied(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-container modal-md">
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon icon-info">
              <KeyRound size={18} />
            </div>
            <div>
              <h3 className="modal-title">Upstox Redirect URL</h3>
              {userName && <span className="modal-subtitle">For user: {userName}</span>}
            </div>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-instruction">
            Register this exact redirect URI in your <strong>Upstox Developer Console</strong> under your app settings.
            Upstox requires this URL to return OAuth tokens upon successful authorization.
          </p>

          <div className="copy-box">
            <input
              type="text"
              readOnly
              value={redirectUri}
              className="copy-input"
            />
            <button
              type="button"
              className={`btn-copy ${copied ? "copied" : ""}`}
              onClick={handleCopy}
            >
              {copied ? (
                <>
                  <Check size={14} />
                  <span>Copied!</span>
                </>
              ) : (
                <>
                  <Copy size={14} />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          <div className="callout-box">
            <ExternalLink size={15} />
            <div className="callout-text">
              Log into <a href="https://account.upstox.com/developer/apps" target="_blank" rel="noreferrer">Upstox Developer Apps</a>,
              select your app, and paste the URL into <strong>Redirect URL</strong>.
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-primary" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
