import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  selected: string[]; // "YYYY-MM-DD"
  onToggle: (date: string) => void;
}

const WEEKDAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"];

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Month-grid calendar for picking several trading dates at once. Weekends are shown but disabled
 * (no market, no point sending them to the backtest); a selected date toggles off on a second click. */
export const BacktestCalendar: React.FC<Props> = ({ selected, onToggle }) => {
  const today = new Date();
  const [cursor, setCursor] = React.useState(new Date(today.getFullYear(), today.getMonth(), 1));

  const firstOfMonth = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Monday-first grid
  const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(cursor.getFullYear(), cursor.getMonth(), i + 1)),
  ];
  const selectedSet = new Set(selected);

  return (
    <div className="backtest-calendar">
      <div className="backtest-calendar__header">
        <button
          type="button"
          className="btn btn--icon btn--ghost"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
          aria-label="Previous month"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="section-title backtest-calendar__month">
          {cursor.toLocaleString("en-US", { month: "long", year: "numeric" })}
        </span>
        <button
          type="button"
          className="btn btn--icon btn--ghost"
          onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
          aria-label="Next month"
        >
          <ChevronRight size={16} />
        </button>
      </div>
      <div className="backtest-calendar__grid backtest-calendar__grid--labels">
        {WEEKDAY_LABELS.map((w, i) => (
          <span key={i} className="backtest-calendar__weekday">
            {w}
          </span>
        ))}
      </div>
      <div className="backtest-calendar__grid">
        {cells.map((d, i) => {
          if (!d) return <span key={i} />;
          const iso = ymd(d);
          const isWeekend = d.getDay() === 0 || d.getDay() === 6;
          const isFuture = d > today;
          const isSelected = selectedSet.has(iso);
          const disabled = isWeekend || isFuture;
          return (
            <button
              type="button"
              key={iso}
              disabled={disabled}
              onClick={() => onToggle(iso)}
              className={`backtest-calendar__day ${isSelected ? "backtest-calendar__day--selected" : ""}`}
              title={disabled ? (isFuture ? "Future date" : "Market closed (weekend)") : iso}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
};
