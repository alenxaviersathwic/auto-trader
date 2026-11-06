import React, { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
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
  // IST trading day, independent of the viewer's own timezone
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).formatToParts(new Date());
  const y = parts.find((p) => p.type === "year")!.value;
  const m = parts.find((p) => p.type === "month")!.value;
  const d = parts.find((p) => p.type === "day")!.value;
  return `${y}-${m}-${d}`;
}

/** Default start: now when it is 09:25 IST or later, otherwise the 09:15 open. Close defaults to 15:45. */
function defaultStartTime(): string {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false }).formatToParts(new Date());
  const hh = parts.find((p) => p.type === "hour")!.value;
  const mm = parts.find((p) => p.type === "minute")!.value;
  const now = `${hh === "24" ? "00" : hh}:${mm}`;
  return now >= "09:25" ? now : "09:15";
}
const INDEX_CLOSE_TIME = "15:45";
const COMMODITY_CLOSE_TIME = "23:00"; // MCX trades in the evening
const closeTimeFor = (scope: "INDEX" | "COMMODITY") => (scope === "COMMODITY" ? COMMODITY_CLOSE_TIME : INDEX_CLOSE_TIME);

const SESSION_TYPE_OPTIONS: Array<{ value: "FULL_AUTO" | "SEMI_AUTO" | "MANUAL"; label: string }> = [
  { value: "MANUAL", label: "Manual" },
  { value: "SEMI_AUTO", label: "Semi-Auto" },
  { value: "FULL_AUTO", label: "Full-Auto" },
];

const DEFAULT_VALUES: SessionCreateFormValues = {
  name: "",
  tradeDate: todayIST(),
  userId: 0,
  capital: 100000,
  maxLossPercentage: 3,
  scope: "INDEX",
  underlyings: [],
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

  useEffect(() => {
    if (isOpen) {
      setServerError(null);
      reset({ ...DEFAULT_VALUES, tradeDate: todayIST(), startTime: defaultStartTime(), closeTime: INDEX_CLOSE_TIME });
    }
  }, [isOpen, reset]);

  const scope = watch("scope");
  const closeTime = watch("closeTime");

  // Switching scope moves the exit time to that scope's default (Index 15:45, Commodity 23:00),
  // unless the user already typed their own time.
  useEffect(() => {
    if (closeTime === INDEX_CLOSE_TIME || closeTime === COMMODITY_CLOSE_TIME) {
      setValue("closeTime", closeTimeFor(scope), { shouldValidate: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);
  const underlyings = watch("underlyings") || [];
  const commodityItems = watch("commodityItems") || [];
  const routeThroughUpstox = watch("routeThroughUpstox");

  // Active users, for the user dropdown
  const { data: userPage } = useUserSearch({ page: 0, limit: 50, status: "ACTIVE" } as any);
  const users = userPage?.list || [];

  // Research Engine's current top-5 INDEX / top-3 COMMODITY picks, for the chip selectors
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

  const rankByScore = (bucketed: typeof indexResults, take: number): string[] => {
    if (!bucketed) return [];
    const all = [
      ...bucketed.suggested,
      ...bucketed.bearishWatch,
      ...bucketed.clearNeutral,
      ...bucketed.hasNegative,
      ...bucketed.mixed,
      ...bucketed.noCoverage,
    ];
    const byCode = new Map<string, number>();
    for (const c of all) {
      const score = c.latestScore ?? c.score ?? 0;
      if (!byCode.has(c.underlyingCode) || (byCode.get(c.underlyingCode) || 0) < score) {
        byCode.set(c.underlyingCode, score);
      }
    }
    return Array.from(byCode.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, take)
      .map(([code]) => code);
  };

  const topIndexItems = useMemo(() => rankByScore(indexResults, 5), [indexResults]);
  const topCommodityItems = useMemo(() => rankByScore(commodityResults, 3), [commodityResults]);

  const toggleChip = (field: "underlyings" | "commodityItems", code: string) => {
    const current = field === "underlyings" ? underlyings : commodityItems;
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
    setValue(field, next, { shouldValidate: true, shouldDirty: true });
  };

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
    <div className={`drawer-overlay ${isOpen ? "open" : ""}`} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer drawer--wide" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h2 className="page-title">New Trading Session</h2>
          <button type="button" className="btn btn--icon" onClick={onClose} disabled={isSubmitting} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-body">
          {serverError && (
            <div className="form-error" style={{ marginBottom: "var(--space-4)" }}>
              {serverError}
            </div>
          )}

          <form id="session-form" onSubmit={handleSubmit(onSubmit)} autoComplete="off">
            <div className="form-grid">
              <div className="form-group form-grid__full">
                <label className="form-label" htmlFor="name">Session Name</label>
                <input
                  id="name"
                  type="text"
                  className="input"
                  placeholder="Optional — auto-generated if left blank"
                  {...register("name")}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="userId">User</label>
                <select id="userId" className={`select ${errors.userId ? "input--error" : ""}`} {...register("userId")}>
                  <option value={0}>Select a user...</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
                {errors.userId && <span className="form-error">{errors.userId.message}</span>}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="capital">Capital (₹)</label>
                <input
                  id="capital"
                  type="number"
                  step="0.01"
                  className={`input ${errors.capital ? "input--error" : ""}`}
                  {...register("capital")}
                />
                {errors.capital && <span className="form-error">{errors.capital.message}</span>}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="maxLossPercentage">Max Loss / Session (%)</label>
                <input
                  id="maxLossPercentage"
                  type="number"
                  step="0.1"
                  className={`input ${errors.maxLossPercentage ? "input--error" : ""}`}
                  {...register("maxLossPercentage")}
                />
                {errors.maxLossPercentage && <span className="form-error">{errors.maxLossPercentage.message}</span>}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="startTime">Start time (IST)</label>
                <input
                  id="startTime"
                  type="time"
                  className={`input ${errors.startTime ? "input--error" : ""}`}
                  {...register("startTime")}
                />
                {errors.startTime && <span className="form-error">{errors.startTime.message}</span>}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="closeTime">Close time (IST)</label>
                <input
                  id="closeTime"
                  type="time"
                  className={`input ${errors.closeTime ? "input--error" : ""}`}
                  {...register("closeTime")}
                />
                {errors.closeTime && <span className="form-error">{errors.closeTime.message}</span>}
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="scope">Scope</label>
                <select id="scope" className="select" {...register("scope")}>
                  <option value="INDEX">Index</option>
                  <option value="COMMODITY">Commodity</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sessionType">Session Type</label>
                <select id="sessionType" className="select" {...register("sessionType")}>
                  {SESSION_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {scope === "INDEX" ? (
                <div className="form-group form-grid__full">
                  <label className="form-label">Index Underlyings (top 5 from Research Engine)</label>
                  <div className="toggle-chip-group">
                    {topIndexItems.length === 0 && (
                      <span className="label text-muted">No research results yet — run the Research Engine first.</span>
                    )}
                    {topIndexItems.map((code) => (
                      <button
                        key={code}
                        type="button"
                        className={`toggle-chip ${underlyings.includes(code) ? "toggle-chip--active" : ""}`}
                        onClick={() => toggleChip("underlyings", code)}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                  {errors.underlyings && <span className="form-error">{errors.underlyings.message as string}</span>}
                </div>
              ) : (
                <div className="form-group form-grid__full">
                  <label className="form-label">Commodities (top 3 from Research Engine)</label>
                  <div className="toggle-chip-group">
                    {topCommodityItems.length === 0 && (
                      <span className="label text-muted">No research results yet — run the Research Engine first.</span>
                    )}
                    {topCommodityItems.map((code) => (
                      <button
                        key={code}
                        type="button"
                        className={`toggle-chip ${commodityItems.includes(code) ? "toggle-chip--active" : ""}`}
                        onClick={() => toggleChip("commodityItems", code)}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                  {errors.commodityItems && <span className="form-error">{errors.commodityItems.message as string}</span>}
                </div>
              )}

              <div className="form-group form-grid__full">
                <label className="form-label">Order Routing</label>
                <div className="toggle-chip-group">
                  <button
                    type="button"
                    className={`toggle-chip ${routeThroughUpstox ? "toggle-chip--active" : ""}`}
                    onClick={() => setValue("routeThroughUpstox", !routeThroughUpstox, { shouldDirty: true })}
                  >
                    {routeThroughUpstox ? "LIVE — orders go to Upstox" : "Simulated — no orders sent"}
                  </button>
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
            {isSubmitting ? "Creating..." : "Create Session"}
          </button>
        </div>
      </div>
    </div>
  );
};
