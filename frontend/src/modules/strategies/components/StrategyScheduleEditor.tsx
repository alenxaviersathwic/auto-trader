import React, { useState } from "react";
import { CalendarDays, Plus, Trash2 } from "lucide-react";
import { DayOverride, WEEKDAY_CODES, WeekdayCode } from "../types/strategies.types";

interface StrategyScheduleEditorProps {
  activeDays: WeekdayCode[];
  dayOverrides: DayOverride[];
  onChange: (next: { activeDays: WeekdayCode[]; dayOverrides: DayOverride[] }) => void;
}

const todayIso = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/**
 * Weekly schedule + date-specific overrides.
 * - activeDays empty  => strategy runs every trading day
 * - override on a date always wins (holiday shift: block old date, run on new date)
 */
export const StrategyScheduleEditor: React.FC<StrategyScheduleEditorProps> = ({
  activeDays,
  dayOverrides,
  onChange,
}) => {
  const [newDate, setNewDate] = useState<string>("");
  const [newActive, setNewActive] = useState<boolean>(true);
  const [newReason, setNewReason] = useState<string>("");
  const [dateError, setDateError] = useState<string | null>(null);
  const [showPast, setShowPast] = useState<boolean>(false);

  const toggleDay = (day: WeekdayCode) => {
    const next = activeDays.includes(day) ? activeDays.filter((d) => d !== day) : [...activeDays, day];
    onChange({
      activeDays: WEEKDAY_CODES.filter((d) => next.includes(d)),
      dayOverrides,
    });
  };

  const addOverride = () => {
    if (!newDate) {
      setDateError("Pick a date");
      return;
    }
    if (dayOverrides.some((o) => o.date === newDate)) {
      setDateError("An override for this date already exists");
      return;
    }
    setDateError(null);
    const next = [...dayOverrides, { date: newDate, active: newActive, reason: newReason.trim() || null }].sort((a, b) =>
      a.date.localeCompare(b.date)
    );
    onChange({ activeDays, dayOverrides: next });
    setNewDate("");
    setNewReason("");
  };

  const removeOverride = (date: string) => {
    onChange({ activeDays, dayOverrides: dayOverrides.filter((o) => o.date !== date) });
  };

  const today = todayIso();
  const pastCount = dayOverrides.filter((o) => o.date < today).length;
  const visible = showPast ? dayOverrides : dayOverrides.filter((o) => o.date >= today);

  return (
    <div className="flex flex-col gap-4">
      <div className="form-group">
        <label className="form-label">Active days</label>
        <div className="flex flex-wrap items-center gap-2">
          {WEEKDAY_CODES.map((day) => {
            const on = activeDays.includes(day);
            return (
              <button
                key={day}
                type="button"
                className={`btn ${on ? "btn--primary" : "btn--ghost"} mono`}
                onClick={() => toggleDay(day)}
                aria-pressed={on}
              >
                {day}
              </button>
            );
          })}
          {activeDays.length > 0 && (
            <button type="button" className="btn btn--ghost micro" onClick={() => onChange({ activeDays: [], dayOverrides })}>
              Clear (every day)
            </button>
          )}
        </div>
        <span className="micro text-muted">
          {activeDays.length === 0
            ? "No days selected — runs every trading day."
            : `Runs only on ${activeDays.join(", ")}.`}
        </span>
      </div>

      <div className="form-group">
        <label className="form-label">Date overrides (holiday shifts, special sessions)</label>
        <div className="flex flex-wrap items-end gap-2">
          <input
            type="date"
            className={`input mono ${dateError ? "input--error" : ""}`}
            value={newDate}
            onChange={(e) => {
              setNewDate(e.target.value);
              setDateError(null);
            }}
          />
          <select
            className="select"
            value={newActive ? "RUN" : "BLOCK"}
            onChange={(e) => setNewActive(e.target.value === "RUN")}
          >
            <option value="RUN">RUN on this date</option>
            <option value="BLOCK">BLOCK this date</option>
          </select>
          <input
            type="text"
            className="input"
            placeholder="Reason, e.g. Diwali — expiry moved to Monday"
            maxLength={200}
            value={newReason}
            onChange={(e) => setNewReason(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <button type="button" className="btn btn--ghost" onClick={addOverride}>
            <Plus size={14} strokeWidth={1.5} /> Add
          </button>
        </div>
        {dateError && <span className="form-error">{dateError}</span>}

        {visible.length === 0 ? (
          <span className="micro text-muted">No upcoming overrides.</span>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Day</th>
                <th>Action</th>
                <th>Reason</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((o) => (
                <tr key={o.date}>
                  <td className="mono">{o.date}</td>
                  <td className="mono">{WEEKDAY_CODES[(new Date(`${o.date}T00:00:00`).getDay() + 6) % 7]}</td>
                  <td>
                    <span className={`badge ${o.active ? "badge--green" : "badge--red"}`}>{o.active ? "RUN" : "BLOCK"}</span>
                  </td>
                  <td>{o.reason || "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      type="button"
                      className="btn btn--icon"
                      title="Remove override"
                      onClick={() => removeOverride(o.date)}
                    >
                      <Trash2 size={14} strokeWidth={1.5} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {pastCount > 0 && (
          <button type="button" className="btn btn--ghost micro" onClick={() => setShowPast((v) => !v)}>
            <CalendarDays size={13} strokeWidth={1.5} /> {showPast ? "Hide" : "Show"} {pastCount} past override
            {pastCount > 1 ? "s" : ""}
          </button>
        )}
      </div>
    </div>
  );
};
