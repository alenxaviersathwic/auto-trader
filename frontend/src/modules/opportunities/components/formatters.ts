export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatExpiry(date: string): string {
  return new Date(`${date}T00:00:00`)
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    .toUpperCase();
}

export function formatRupee(value: number): string {
  return `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatCompactRupee(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 100000) {
    return `${sign}₹${(abs / 100000).toFixed(2)}L`;
  }
  if (abs >= 1000) {
    return `${sign}₹${(abs / 1000).toFixed(1)}k`;
  }
  return `${sign}₹${abs.toFixed(0)}`;
}

export function getMoneyness(spot: number, strike: number, optionType: "CE" | "PE"): {
  label: "ATM" | "ITM" | "OTM";
  diff: number;
  diffFormatted: string;
} {
  if (!spot || !strike) {
    return { label: "ATM", diff: 0, diffFormatted: "ATM" };
  }
  const diff = optionType === "CE" ? strike - spot : spot - strike;
  const pct = Math.abs((strike - spot) / spot) * 100;
  
  if (pct < 0.35) {
    return { label: "ATM", diff, diffFormatted: "ATM" };
  }
  if (diff > 0) {
    return { label: "OTM", diff, diffFormatted: `OTM (+${Math.abs(diff).toFixed(0)} pts)` };
  }
  return { label: "ITM", diff, diffFormatted: `ITM (-${Math.abs(diff).toFixed(0)} pts)` };
}


