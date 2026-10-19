import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  X,
  User as UserIcon,
  Key,
  Lock,
  Smartphone,
  ShieldAlert,
  Copy,
  Check,
  Zap,
  ExternalLink,
  Eye,
  EyeOff,
  ClipboardPaste,
} from "lucide-react";
import { User, UserCreatePayload, UserUpdatePayload } from "../types/users.types";
import {
  userCreateSchema,
  userUpdateSchema,
  UserCreateFormValues,
  UserUpdateFormValues,
} from "../schemas/usersForm.schema";
import { ApiError } from "../../../core/api/apiError";
import { copyToClipboard, readFromClipboard } from "../../../core/utils/clipboard";

interface UserDialogProps {
  isOpen: boolean;
  userToEdit: User | null; // null if creating
  onClose: () => void;
  onCreate: (payload: UserCreatePayload) => Promise<User>;
  onUpdate: (id: number, payload: UserUpdatePayload) => Promise<User>;
}

export const UserDialog: React.FC<UserDialogProps> = ({
  isOpen,
  userToEdit,
  onClose,
  onCreate,
  onUpdate,
}) => {
  const isEditing = !!userToEdit;
  // Step 1: Form input, Step 2: Redirect URI info (after create)
  const [step, setStep] = useState<1 | 2>(1);
  const [createdUser, setCreatedUser] = useState<User | null>(null);
  const [copied, setCopied] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  // Field visibility toggles
  const [showSecret, setShowSecret] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [showTotp, setShowTotp] = useState(false);

  // Quick feedback state for pasted fields
  const [pastedField, setPastedField] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<UserCreateFormValues | UserUpdateFormValues>({
    resolver: zodResolver(isEditing ? userUpdateSchema : userCreateSchema),
    defaultValues: {
      name: "",
      apiKey: "",
      apiSecret: "",
      mobile: "",
      pin: "",
      totpSecret: "",
      autoAuthEnabled: true,
    },
  });

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setServerError(null);
      setCopied(false);
      setCreatedUser(null);
      setShowSecret(false);
      setShowPin(false);
      setShowTotp(false);
      setPastedField(null);

      if (userToEdit) {
        reset({
          name: userToEdit.name,
          apiKey: userToEdit.upstox?.apiKey || "",
          apiSecret: "", // Blank in edit mode so existing stays unchanged
          mobile: userToEdit.upstox?.mobile || "",
          pin: "", // Blank in edit mode so existing stays unchanged
          totpSecret: "", // Blank in edit mode so existing stays unchanged
          autoAuthEnabled: userToEdit.upstox?.autoAuthEnabled ?? true,
        });
      } else {
        reset({
          name: "",
          apiKey: "",
          apiSecret: "",
          mobile: "",
          pin: "",
          totpSecret: "",
          autoAuthEnabled: true,
        });
      }
    }
  }, [isOpen, userToEdit, reset]);

  if (!isOpen) return null;

  const handlePasteIntoField = async (
    fieldName: "apiKey" | "apiSecret" | "totpSecret" | "pin"
  ) => {
    const text = await readFromClipboard();
    if (text !== null && text !== undefined) {
      // Clean string: trim and remove spaces if TOTP
      let cleaned = text.trim();
      if (fieldName === "totpSecret") {
        cleaned = cleaned.replace(/\s+/g, "").toUpperCase();
      }
      setValue(fieldName, cleaned, { shouldValidate: true, shouldDirty: true });
      setPastedField(fieldName);
      setTimeout(() => setPastedField(null), 1500);
    }
  };

  const onSubmit = async (values: any) => {
    setServerError(null);
    try {
      if (isEditing && userToEdit) {
        const updatePayload: UserUpdatePayload = {
          name: values.name.trim(),
          apiKey: values.apiKey.trim(),
          mobile: values.mobile.trim(),
          autoAuthEnabled: values.autoAuthEnabled,
        };
        // Only send secrets if modified
        if (values.apiSecret && values.apiSecret.trim()) {
          updatePayload.apiSecret = values.apiSecret.trim();
        }
        if (values.pin && values.pin.trim()) {
          updatePayload.pin = values.pin.trim();
        }
        if (values.totpSecret && values.totpSecret.trim()) {
          updatePayload.totpSecret = values.totpSecret.trim().replace(/\s+/g, "").toUpperCase();
        }

        await onUpdate(userToEdit.id, updatePayload);
        onClose();
      } else {
        const createPayload: UserCreatePayload = {
          name: values.name.trim(),
          apiKey: values.apiKey.trim(),
          apiSecret: values.apiSecret.trim(),
          mobile: values.mobile.trim(),
          pin: values.pin.trim(),
          totpSecret: values.totpSecret.trim().replace(/\s+/g, "").toUpperCase(),
          autoAuthEnabled: values.autoAuthEnabled ?? true,
        };

        const res = await onCreate(createPayload);
        setCreatedUser(res);
        // Switch to Step 2: Redirect URI
        setStep(2);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setServerError(err.message);
        if (Array.isArray(err.error)) {
          err.error.forEach((fe: any) => {
            if (fe.field) {
              setError(fe.field as any, { message: fe.message });
            }
          });
        }
      } else {
        setServerError(err?.message || "Failed to save user account");
      }
    }
  };

  const handleCopyRedirectUri = async () => {
    if (!createdUser?.upstox?.redirectUri) return;
    const ok = await copyToClipboard(createdUser.upstox.redirectUri);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    }
  };

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-container modal-lg">
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-icon icon-primary">
              <UserIcon size={18} />
            </div>
            <div>
              <h3 className="modal-title">
                {step === 2
                  ? "Register Redirect URL in Upstox"
                  : isEditing
                  ? `Edit User: ${userToEdit?.name}`
                  : "Add Upstox User"}
              </h3>
              <span className="modal-subtitle">
                {step === 2
                  ? "Step 2 of 2: OAuth Configuration"
                  : isEditing
                  ? "Update trading profile and credentials"
                  : "Step 1 of 2: Profile & Credentials"}
              </span>
            </div>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {serverError && (
            <div className="form-error-alert">
              <ShieldAlert size={16} />
              <span>{serverError}</span>
            </div>
          )}

          {step === 1 ? (
            <form
              id="user-form"
              onSubmit={handleSubmit(onSubmit)}
              className="user-form-grid"
              autoComplete="off"
            >
              {/* Account Name */}
              <div className="form-group full-width">
                <label className="form-label" htmlFor="name">
                  User / Account Name <span className="req">*</span>
                </label>
                <div className={`input-wrap ${errors.name ? "input-err" : ""}`}>
                  <UserIcon size={16} className="input-icon" />
                  <input
                    id="name"
                    type="text"
                    autoComplete="off"
                    spellCheck="false"
                    className="form-input"
                    placeholder="e.g., Primary Trading Account"
                    {...register("name")}
                  />
                </div>
                {errors.name && (
                  <span className="field-error">{errors.name.message}</span>
                )}
              </div>

              {/* Upstox API Key */}
              <div className="form-group">
                <div className="form-label-row">
                  <label className="form-label" htmlFor="apiKey">
                    Upstox API Key <span className="req">*</span>
                  </label>
                  {pastedField === "apiKey" && (
                    <span className="field-pasted-tag">Pasted!</span>
                  )}
                </div>
                <div className={`input-wrap ${errors.apiKey ? "input-err" : ""}`}>
                  <Key size={16} className="input-icon" />
                  <input
                    id="apiKey"
                    type="text"
                    autoComplete="off"
                    spellCheck="false"
                    className="form-input font-mono"
                    placeholder="e.g., f8d2b7c4-..."
                    {...register("apiKey")}
                  />
                  <button
                    type="button"
                    className="input-inline-btn"
                    title="Paste API Key from Clipboard"
                    onClick={() => handlePasteIntoField("apiKey")}
                  >
                    <ClipboardPaste size={14} />
                    <span className="inline-btn-text">Paste</span>
                  </button>
                </div>
                {errors.apiKey && (
                  <span className="field-error">{errors.apiKey.message}</span>
                )}
              </div>

              {/* Upstox API Secret */}
              <div className="form-group">
                <div className="form-label-row">
                  <label className="form-label" htmlFor="apiSecret">
                    Upstox API Secret {isEditing ? "(Optional)" : <span className="req">*</span>}
                  </label>
                  {pastedField === "apiSecret" && (
                    <span className="field-pasted-tag">Pasted!</span>
                  )}
                </div>
                <div className={`input-wrap ${errors.apiSecret ? "input-err" : ""}`}>
                  <Lock size={16} className="input-icon" />
                  <input
                    id="apiSecret"
                    type={showSecret ? "text" : "password"}
                    autoComplete="new-password"
                    spellCheck="false"
                    className="form-input font-mono"
                    placeholder={
                      isEditing
                        ? userToEdit?.upstox?.hasApiSecret
                          ? "••••• saved (leave blank to keep)"
                          : "Enter new secret"
                        : "Enter API Secret"
                    }
                    {...register("apiSecret")}
                  />
                  <button
                    type="button"
                    className="input-inline-btn"
                    title="Paste Secret from Clipboard"
                    onClick={() => handlePasteIntoField("apiSecret")}
                  >
                    <ClipboardPaste size={14} />
                    <span className="inline-btn-text">Paste</span>
                  </button>
                  <button
                    type="button"
                    className="input-inline-icon-btn"
                    onClick={() => setShowSecret(!showSecret)}
                    title={showSecret ? "Hide secret" : "Show secret"}
                  >
                    {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {errors.apiSecret && (
                  <span className="field-error">{errors.apiSecret.message}</span>
                )}
              </div>

              {/* Mobile Number */}
              <div className="form-group">
                <label className="form-label" htmlFor="mobile">
                  Registered Mobile <span className="req">*</span>
                </label>
                <div className={`input-wrap ${errors.mobile ? "input-err" : ""}`}>
                  <Smartphone size={16} className="input-icon" />
                  <input
                    id="mobile"
                    type="tel"
                    autoComplete="off"
                    maxLength={10}
                    className="form-input"
                    placeholder="e.g., 9876543210"
                    {...register("mobile")}
                  />
                </div>
                {errors.mobile && (
                  <span className="field-error">{errors.mobile.message}</span>
                )}
              </div>

              {/* Upstox PIN */}
              <div className="form-group">
                <label className="form-label" htmlFor="pin">
                  Upstox Login PIN {isEditing ? "(Optional)" : <span className="req">*</span>}
                </label>
                <div className={`input-wrap ${errors.pin ? "input-err" : ""}`}>
                  <Lock size={16} className="input-icon" />
                  <input
                    id="pin"
                    type={showPin ? "text" : "password"}
                    inputMode="numeric"
                    maxLength={6}
                    autoComplete="new-password"
                    className="form-input tracking-widest"
                    placeholder={
                      isEditing
                        ? userToEdit?.upstox?.hasPin
                          ? "•••••• saved (leave blank)"
                          : "6-digit PIN"
                        : "6-digit PIN"
                    }
                    {...register("pin")}
                  />
                  <button
                    type="button"
                    className="input-inline-icon-btn"
                    onClick={() => setShowPin(!showPin)}
                    title={showPin ? "Hide PIN" : "Show PIN"}
                  >
                    {showPin ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {errors.pin && (
                  <span className="field-error">{errors.pin.message}</span>
                )}
              </div>

              {/* TOTP Secret */}
              <div className="form-group full-width">
                <div className="form-label-row">
                  <label className="form-label" htmlFor="totpSecret">
                    TOTP Secret Key {isEditing ? "(Optional)" : <span className="req">*</span>}
                  </label>
                  {pastedField === "totpSecret" && (
                    <span className="field-pasted-tag">Pasted!</span>
                  )}
                </div>
                <div className={`input-wrap ${errors.totpSecret ? "input-err" : ""}`}>
                  <Key size={16} className="input-icon" />
                  <input
                    id="totpSecret"
                    type={showTotp ? "text" : "password"}
                    autoComplete="new-password"
                    spellCheck="false"
                    className="form-input font-mono"
                    placeholder={
                      isEditing
                        ? userToEdit?.upstox?.hasTotpSecret
                          ? "••••• saved (leave blank to keep)"
                          : "Base32 TOTP Secret from Upstox"
                        : "Base32 TOTP secret from Upstox 2FA setup"
                    }
                    {...register("totpSecret")}
                  />
                  <button
                    type="button"
                    className="input-inline-btn"
                    title="Paste TOTP Secret from Clipboard"
                    onClick={() => handlePasteIntoField("totpSecret")}
                  >
                    <ClipboardPaste size={14} />
                    <span className="inline-btn-text">Paste</span>
                  </button>
                  <button
                    type="button"
                    className="input-inline-icon-btn"
                    onClick={() => setShowTotp(!showTotp)}
                    title={showTotp ? "Hide TOTP" : "Show TOTP"}
                  >
                    {showTotp ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {errors.totpSecret && (
                  <span className="field-error">{errors.totpSecret.message}</span>
                )}
                <span className="field-help">
                  Needed for headless auto-authentication without manual OTP entry. Spaces are automatically stripped.
                </span>
              </div>

              {/* Auto-Auth Toggle */}
              <div className="form-group full-width toggle-row">
                <div className="toggle-info">
                  <div className="toggle-title">
                    <Zap size={15} className="text-emerald" />
                    <span>Enable Daily Auto-Authentication</span>
                  </div>
                  <span className="toggle-desc">
                    Automatically renews Upstox token prior to market open (Asia/Kolkata).
                  </span>
                </div>
                <label className="switch">
                  <input
                    type="checkbox"
                    {...register("autoAuthEnabled")}
                  />
                  <span className="slider round"></span>
                </label>
              </div>
            </form>
          ) : (
            /* Step 2: Redirect URI Registration */
            <div className="redirect-step-container">
              <div className="step-success-box">
                <Check size={20} className="text-emerald" />
                <div>
                  <h4 className="success-heading">Account Created Successfully!</h4>
                  <p className="success-sub">
                    User <strong>{createdUser?.name}</strong> has been created.
                    {createdUser?.isDefault && " Set as primary default account."}
                  </p>
                </div>
              </div>

              <div className="redirect-instruction-section">
                <h4 className="step-instruction-title">
                  Register this redirect URL in your Upstox app:
                </h4>
                <p className="step-instruction-desc">
                  To enable automated and OAuth logins, paste the following URL into your Upstox developer console:
                </p>

                <div className="copy-box">
                  <input
                    type="text"
                    readOnly
                    value={createdUser?.upstox?.redirectUri || ""}
                    className="copy-input"
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    type="button"
                    className={`btn-copy ${copied ? "copied" : ""}`}
                    onClick={handleCopyRedirectUri}
                  >
                    {copied ? (
                      <>
                        <Check size={14} />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={14} />
                        <span>Copy URL</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="callout-box">
                  <ExternalLink size={15} />
                  <div className="callout-text">
                    Upstox App Settings &gt; Redirect URL &gt; Paste URL &gt; Save Changes.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          {step === 1 ? (
            <>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                form="user-form"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? "Saving..."
                  : isEditing
                  ? "Save Changes"
                  : "Create User & Continue"}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onClose}
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
