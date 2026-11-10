import React, { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  Hand,
  Layers,
  ShieldAlert,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import { sessionCreateSchema, SessionCreateFormValues } from "../schemas/sessionForm.schema";
import { TradingSessionCreatePayload } from "../types/sessions.types";
import { ApiError } from "../../../core/api/apiError";
import { useUserSearch } from "../../users/hooks/useUsers";
import { researchApi } from "../../research/api/research.api";

interface SessionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (payload: TradingSessionCreatePayload) => Promise<unknown>;
}

function todayIST(): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).formatToParts(new Date());
  const y = parts.find((p) => p.type === "year")!.value;
  const m = parts.find((p) => p.type === "month")!.value;
  const d = parts.find((p) => p.type === "day")!.value;
  return `${y}-${m}-${d}`;
}

function defaultStartTime(): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const hh = parts.find((p) => p.type === "hour")!.value;
  const mm = parts.find((p) => p.type === "minute")!.value;
  const now = `${hh === "24" ? "00" : hh}:${mm}`;
  if (now >= "15:30") return "09:15";
  return now >= "09:25" ? now : "09:15";
}

const INDEX_CLOSE_TIME = "15:45";
const COMMODITY_CLOSE_TIME = "23:00";
const FALLBACK_INDICES = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"];
const FALLBACK_COMMODITIES = ["CRUDEOIL", "NATURALGAS", "GOLDM"];

const closeTimeFor = (scope: "INDEX" | "COMMODITY") =>
  scope === "COMMODITY" ? COMMODITY_CLOSE_TIME : INDEX_CLOSE_TIME;

const SESSION_MODES: Array<{
  value: "MANUAL" | "SEMI_AUTO" | "FULL_AUTO";
  label: string;
  tag: string;
  desc: string;
  icon: React.ReactNode;
}> = [
  {
    value: "MANUAL",
    label: "Manual",
    tag: "4 PICKS",
    desc: "Offers top 4 live setups. You lock the pick and confirm entry price & lots in the Trader modal.",
    icon: <Hand size={14} className="text-blue" />,
  },
  {
    value: "SEMI_AUTO",
    label: "Semi-Auto",
    tag: "AUTO-LOCK",
    desc: "Session loop automatically selects and locks the #1 highest-ranked opportunity for 1-click confirmation.",
    icon: <Cpu size={14} className="text-amber" />,
  },
  {
    value: "FULL_AUTO",
    label: "Full-Auto",
    tag: "AUTONOMOUS",
    desc: "Auto-selects, locks & enters the #1 pick into its Trader loop; trails SL & exits in best condition.",
    icon: <Bot size={14} className="text-green" />,
  },
];

const DEFAULT_VALUES: SessionCreateFormValues = {
  name: "",
  tradeDate: todayIST(),
  userId: 0,
  capital: 100000,
  maxLossPercentage: 3,
  scope: "INDEX",
  underlyings: ["NIFTY"],
  commodityItems: [],
  sessionType: "MANUAL",
  routeThroughUpstox: false,
  startTime: defaultStartTime(),
  closeTime: INDEX_CLOSE_TIME,
};

export const SessionDialog: React.FC<SessionDialogProps> = ({ isOpen, onClose, onCreate }) => {
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SessionCreateFormValues>({
    resolver: zodResolver(sessionCreateSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const { data: userPage } = useUserSearch({ page: 0, limit: 50, status: "ACTIVE" } as any);
  const users = userPage?.list || [];

  useEffect(() => {
    if (isOpen) {
      setServerError(null);
      const defaultUser = users.find((u: any) => u.isDefault) || users[0];
      reset({
        ...DEFAULT_VALUES,
        userId: defaultUser ? Number(defaultUser.id) : 0,
        tradeDate: todayIST(),
        startTime: defaultStartTime(),
        closeTime: INDEX_CLOSE_TIME,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, reset, users.length]);

  const scope = watch("scope");
  const sessionType = watch("sessionType");
  const userId = Number(watch("userId") || 0);
  const capital = Number(watch("capital") || 0);
  const maxLossPercentage = Number(watch("maxLossPercentage") || 0);
  const startTime = watch("startTime");
  const closeTime = watch("closeTime");
  const underlyings = watch("underlyings") || [];
  const commodityItems = watch("commodityItems") || [];
  const routeThroughUpstox = Boolean(watch("routeThroughUpstox"));

  const selectedUser = useMemo(
    () => users.find((u: any) => Number(u.id) === userId),
    [users, userId],
  );

  useEffect(() => {
    if (closeTime === INDEX_CLOSE_TIME || closeTime === COMMODITY_CLOSE_TIME) {
      setValue("closeTime", closeTimeFor(scope), { shouldValidate: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const { data: indexResults } = useQuery({
    queryKey: ["sessions", "research-latest", "INDEX"],
    queryFn: () => researchApi.getLatestResults("INDEX"),
    enabled: isOpen,
  });
  const { data: commodityResults } = useQuery({
    queryKey: ["sessions", "research-latest", "COMMODITY"],
    queryFn: () => researchApi.getLatestResults("COMMODITY"),
    enabled: isOpen,
  });

  const rankByScore = (bucketed: typeof indexResults, take: number, fallback: string[]): string[] => {
    if (!bucketed) return fallback;
    const all = [
      ...bucketed.suggested,
      ...bucketed.bearishWatch,
      ...bucketed.clearNeutral,
      ...bucketed.hasNegative,
      ...bucketed.mixed,
      ...bucketed.noCoverage,
    ];
    if (all.length === 0) return fallback;
    const byCode = new Map<string, number>();
    for (const c of all) {
      const score = c.latestScore ?? c.score ?? 0;
      if (!byCode.has(c.underlyingCode) || (byCode.get(c.underlyingCode) || 0) < score) {
        byCode.set(c.underlyingCode, score);
      }
    }
    const ranked = Array.from(byCode.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, take)
      .map(([code]) => code);
    return ranked.length > 0 ? ranked : fallback;
  };

  const topIndexItems = useMemo(() => rankByScore(indexResults, 5, FALLBACK_INDICES), [indexResults]);
  const topCommodityItems = useMemo(
    () => rankByScore(commodityResults, 3, FALLBACK_COMMODITIES),
    [commodityResults],
  );

  const toggleChip = (field: "underlyings" | "commodityItems", code: string) => {
    const current = field === "underlyings" ? underlyings : commodityItems;
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
    setValue(field, next, { shouldValidate: true, shouldDirty: true });
  };

  const maxLossRupees = Math.max(0, (capital * maxLossPercentage) / 100);

  const onSubmit = async (values: SessionCreateFormValues) => {
    setServerError(null);
    try {
      const payload: TradingSessionCreatePayload = {
        ...values,
        tradeDate: todayIST(),
        name: values.name?.trim() || undefined,
      };
      await onCreate(payload);
      onClose();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setServerError(err.message);
        if (Array.isArray(err.error)) {
          err.error.forEach((fe: any) => {
            if (fe.field) setError(fe.field as any, { message: fe.message });
          });
        }
      } else {
        setServerError(err?.message || "Failed to create trading session");
      }
    }
  };

  return (
    <div
      className={`drawer-overlay ${isOpen ? "open" : ""}`}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="drawer drawer--wide" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <div className="header-icon-box">
              <Activity size={18} className="text-blue" />
            </div>
            <div>
              <h2 className="page-title" style={{ fontSize: "1.05rem" }}>
                New Trading Session
              </h2>
              <p className="text-secondary micro">
                Configure capital, automation mode, underlyings &amp; Upstox order execution
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn btn--icon"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="drawer-body">
          {serverError && (
            <div className="form-error" style={{ marginBottom: "var(--space-4)" }}>
              {serverError}
            </div>
          )}

          {/* Executive Live Session Preview Strip */}
          <div className="session-summary-strip">
            <div className="session-summary-cell">
              <span className="session-summary-label">Session Capital</span>
              <span className="session-summary-value">
                ₹{capital > 0 ? capital.toLocaleString("en-IN") : "0"}
              </span>
            </div>
            <div className="session-summary-cell">
              <span className="session-summary-label">Max Loss Budget ({maxLossPercentage || 0}%)</span>
              <span className="session-summary-value text-red">
                -₹{maxLossRupees.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="session-summary-cell">
              <span className="session-summary-label">Session Hours (IST)</span>
              <span className="session-summary-value">
                {startTime || "09:15"} – {closeTime || "15:45"}
              </span>
            </div>
            <div className="session-summary-cell">
              <span className="session-summary-label">Parallel Traders</span>
              <span className="session-summary-value text-green">Max 3 Active</span>
            </div>
          </div>

          <form id="session-form" onSubmit={handleSubmit(onSubmit)} autoComplete="off">
            {/* Section 1: Identity, Capital & Risk Window */}
            <div className="session-section-card">
              <div className="session-section-head">
                <span className="session-section-title">
                  <Wallet size={14} className="text-blue" />
                  <span>1. Account, Capital &amp; Trading Window</span>
                </span>
                {selectedUser && (
                  <span
                    className={`badge ${
                      (selectedUser as any).tokenStatus === "VALID" ? "badge--green" : "badge--amber"
                    }`}
                  >
                    {(selectedUser as any).tokenStatus === "VALID"
                      ? "UPSTOX TOKEN READY"
                      : "CHECK UPSTOX TOKEN"}
                  </span>
                )}
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label" htmlFor="userId">
                    Trading Account (User)
                  </label>
                  <select
                    id="userId"
                    className={`select ${errors.userId ? "input--error" : ""}`}
                    {...register("userId")}
                  >
                    <option value={0}>Select a user...</option>
                    {users.map((u: any) => (
                      <option key={u.id} value={u.id}>
                        {u.name} {u.isDefault ? "(Default)" : ""}
                      </option>
                    ))}
                  </select>
                  {errors.userId && <span className="form-error">{errors.userId.message}</span>}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="name">
                    Session Name <span className="text-muted">(Optional)</span>
                  </label>
                  <input
                    id="name"
                    type="text"
                    className="input"
                    placeholder="Auto-generated from date + underlyings"
                    {...register("name")}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="capital">
                    Session Capital (₹)
                  </label>
                  <input
                    id="capital"
                    type="number"
                    step="1000"
                    className={`input font-mono ${errors.capital ? "input--error" : ""}`}
                    {...register("capital")}
                  />
                  {errors.capital && <span className="form-error">{errors.capital.message}</span>}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="maxLossPercentage">
                    Max Loss Halt (% of Capital)
                  </label>
                  <input
                    id="maxLossPercentage"
                    type="number"
                    step="0.5"
                    className={`input font-mono ${errors.maxLossPercentage ? "input--error" : ""}`}
                    {...register("maxLossPercentage")}
                  />
                  {errors.maxLossPercentage && (
                    <span className="form-error">{errors.maxLossPercentage.message}</span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="startTime">
                    <Clock size={12} style={{ display: "inline", marginRight: 4 }} />
                    Start Time (IST)
                  </label>
                  <input
                    id="startTime"
                    type="time"
                    className={`input font-mono ${errors.startTime ? "input--error" : ""}`}
                    {...register("startTime")}
                  />
                  {errors.startTime && <span className="form-error">{errors.startTime.message}</span>}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="closeTime">
                    <Clock size={12} style={{ display: "inline", marginRight: 4 }} />
                    Close Time (IST)
                  </label>
                  <input
                    id="closeTime"
                    type="time"
                    className={`input font-mono ${errors.closeTime ? "input--error" : ""}`}
                    {...register("closeTime")}
                  />
                  {errors.closeTime && <span className="form-error">{errors.closeTime.message}</span>}
                </div>
              </div>
            </div>

            {/* Section 2: Session Execution Mode (Manual / Semi-Auto / Full-Auto) */}
            <div className="session-section-card">
              <div className="session-section-head">
                <span className="session-section-title">
                  <Bot size={14} className="text-blue" />
                  <span>2. Trader Execution Mode</span>
                </span>
                <span className="badge badge--blue">{sessionType}</span>
              </div>

              <div className="session-mode-grid">
                {SESSION_MODES.map((m) => {
                  const active = sessionType === m.value;
                  return (
                    <button
                      key={m.value}
                      type="button"
                      className={`session-mode-card ${active ? "session-mode-card--active" : ""}`}
                      onClick={() => setValue("sessionType", m.value, { shouldDirty: true })}
                    >
                      <div className="session-mode-card__top">
                        <span
                          className="session-mode-card__title"
                          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                        >
                          {m.icon}
                          {m.label}
                        </span>
                        <span className={`badge ${active ? "badge--blue" : "badge--slate"}`}>
                          {m.tag}
                        </span>
                      </div>
                      <span className="session-mode-card__desc">{m.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Section 3: Scope & Underlyings */}
            <div className="session-section-card">
              <div className="session-section-head">
                <span className="session-section-title">
                  <Layers size={14} className="text-blue" />
                  <span>3. Market Scope &amp; Underlyings</span>
                </span>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <button
                    type="button"
                    className={`toggle-chip ${scope === "INDEX" ? "toggle-chip--active" : ""}`}
                    onClick={() => setValue("scope", "INDEX", { shouldValidate: true })}
                  >
                    INDEX (NSE / BSE)
                  </button>
                  <button
                    type="button"
                    className={`toggle-chip ${scope === "COMMODITY" ? "toggle-chip--active" : ""}`}
                    onClick={() => setValue("scope", "COMMODITY", { shouldValidate: true })}
                  >
                    COMMODITY (MCX)
                  </button>
                </div>
              </div>

              {scope === "INDEX" ? (
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "var(--space-2)",
                    }}
                  >
                    <span className="label text-secondary">
                      Select Index Underlyings ({underlyings.length} selected)
                    </span>
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                        onClick={() =>
                          setValue("underlyings", topIndexItems, {
                            shouldValidate: true,
                            shouldDirty: true,
                          })
                        }
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                        onClick={() =>
                          setValue("underlyings", [], { shouldValidate: true, shouldDirty: true })
                        }
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="toggle-chip-group">
                    {topIndexItems.map((code) => {
                      const active = underlyings.includes(code);
                      return (
                        <button
                          key={code}
                          type="button"
                          className={`toggle-chip ${active ? "toggle-chip--active" : ""}`}
                          onClick={() => toggleChip("underlyings", code)}
                        >
                          {active && <CheckCircle2 size={12} />}
                          <span>{code}</span>
                        </button>
                      );
                    })}
                  </div>
                  {errors.underlyings && (
                    <span className="form-error" style={{ display: "block", marginTop: 6 }}>
                      {errors.underlyings.message as string}
                    </span>
                  )}
                </div>
              ) : (
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "var(--space-2)",
                    }}
                  >
                    <span className="label text-secondary">
                      Select MCX Commodities ({commodityItems.length} selected)
                    </span>
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                        onClick={() =>
                          setValue("commodityItems", topCommodityItems, {
                            shouldValidate: true,
                            shouldDirty: true,
                          })
                        }
                      >
                        Select All
                      </button>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                        onClick={() =>
                          setValue("commodityItems", [], {
                            shouldValidate: true,
                            shouldDirty: true,
                          })
                        }
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="toggle-chip-group">
                    {topCommodityItems.map((code) => {
                      const active = commodityItems.includes(code);
                      return (
                        <button
                          key={code}
                          type="button"
                          className={`toggle-chip ${active ? "toggle-chip--active" : ""}`}
                          onClick={() => toggleChip("commodityItems", code)}
                        >
                          {active && <CheckCircle2 size={12} />}
                          <span>{code}</span>
                        </button>
                      );
                    })}
                  </div>
                  {errors.commodityItems && (
                    <span className="form-error" style={{ display: "block", marginTop: 6 }}>
                      {errors.commodityItems.message as string}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Section 4: Upstox Direct Order Routing Toggle Switch */}
            <div
              role="switch"
              aria-checked={routeThroughUpstox}
              tabIndex={0}
              className={`upstox-toggle-card ${routeThroughUpstox ? "upstox-toggle-card--live" : ""}`}
              onClick={() =>
                setValue("routeThroughUpstox", !routeThroughUpstox, { shouldDirty: true })
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setValue("routeThroughUpstox", !routeThroughUpstox, { shouldDirty: true });
                }
              }}
            >
              <div className="upstox-toggle-card__left">
                <div className="upstox-toggle-card__icon">
                  {routeThroughUpstox ? <Zap size={18} /> : <ShieldAlert size={18} />}
                </div>
                <div>
                  <div className="upstox-toggle-card__title">
                    <span>Upstox Direct Order Execution (`routeThroughUpstox`)</span>
                    <span className={`badge ${routeThroughUpstox ? "badge--green" : "badge--slate"}`}>
                      {routeThroughUpstox ? "LIVE UPSTOX ORDERS ON" : "SIMULATED MODE"}
                    </span>
                  </div>
                  <p className="upstox-toggle-card__desc">
                    {routeThroughUpstox
                      ? "ENABLED — Places real intraday MARKET BUY orders on entry and SELL orders on exit directly via Upstox HFT API (api-hft.upstox.com/v2/order/place)."
                      : "DISABLED — Paper execution mode. The Trader loop streams live Upstox LTP & 1m candles and trails SL/target without sending real broker orders."}
                  </p>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <span
                  className="font-mono micro"
                  style={{
                    fontWeight: 700,
                    color: routeThroughUpstox ? "var(--bullish-green)" : "var(--text-muted)",
                  }}
                >
                  {routeThroughUpstox ? "ON" : "OFF"}
                </span>
                <div className={`upstox-switch-track ${routeThroughUpstox ? "upstox-switch-track--on" : ""}`}>
                  <div className="upstox-switch-thumb" />
                </div>
              </div>
            </div>
          </form>
        </div>

        <div className="drawer-footer">
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" form="session-form" className="btn btn--primary" disabled={isSubmitting}>
            {isSubmitting
              ? "Creating..."
              : routeThroughUpstox
                ? "Create Live Upstox Session"
                : "Create Session"}
          </button>
        </div>
      </div>
    </div>
  );
};
