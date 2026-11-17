import { useRecentIterations } from "../../opportunity-finder/hooks/useOpportunities";
import { FibWatch, NowRead, OpportunityCardItem } from "../../opportunity-finder/types/opportunities.types";
import { TraderCode } from "../../trade-history/types/trades.types";

export const FIB_STAGE: Record<FibWatch["stage"], { label: string; short: string; tone: string; rank: number }> = {
  IN_POCKET: { label: "IN POCKET", short: "in pocket", tone: "green", rank: 4 },
  SHALLOW: { label: "WAITING FOR POCKET", short: "waiting pocket", tone: "blue", rank: 3 },
  STALE: { label: "STALE", short: "stale swing", tone: "amber", rank: 2 },
  FAILED: { label: "SWING FAILED", short: "swing failed", tone: "red", rank: 1 },
  NO_SWING: { label: "NO SWING", short: "no swing", tone: "", rank: 0 },
};

export interface TraderWait {
  /** One line for the compact strip. */
  short: string;
  tone: string;
  fib: FibWatch[];
  flow: { name: string; side: string; reason: string; at: string }[];
  /** Fallback text when the trader has nothing specific to report. */
  idle: string;
}

export interface IndexToday {
  loading: boolean;
  hasScan: boolean;
  spot: number | null;
  /** The temporary trend: the last ~60 minutes (null on scans from before the backend had it). The overall
   *  trend is the Research Engine's job, so the Traders area shows only this. */
  now: NowRead | null;
  wait: TraderWait;
  scans: { id: number; at: string; result: string; text: string }[];
}

/** Today's read of one index for one trader: the temporary (last ~60 min) trend plus what THIS trader is waiting for. */
export function useIndexToday(card: OpportunityCardItem, trader: TraderCode): IndexToday {
  const its = useRecentIterations(card.master?.id ?? null, 12);
  const list = its.data?.list ?? [];
  const last = list[0];
  const d = last?.details;

  const fib = (d?.fibWatch ?? []).filter((w) => w.stage !== "NO_SWING" || (d?.fibWatch ?? []).length === 1);
  const flow = Array.from(
    new Map(
      list.flatMap((it) =>
        (it.details?.setupsRejected ?? []).map(
          (r) => [`${r.name}/${r.side}`, { name: r.name, side: r.side, reason: r.reason, at: it.createdAt }] as const,
        ),
      ),
    ).values(),
  )
    .filter((r) => r.name !== "FIB_GOLDEN_POCKET")
    .slice(0, 4);

  const idle = !last ? "no scan yet" : last.result === "NO_SETUP" ? "no setup in recent scans" : (last.summary ?? last.result.toLowerCase());
  let short = idle;
  let tone = "";
  if (trader === "FIB_GOLDEN_TRADER" && fib.length) {
    const best = [...fib].sort((a, b) => FIB_STAGE[b.stage].rank - FIB_STAGE[a.stage].rank)[0];
    short = `${best.side} ${FIB_STAGE[best.stage].short}`;
    tone = FIB_STAGE[best.stage].tone;
  } else if (trader === "FLOW_MOMENTUM_TRADER" && flow.length) {
    short = `${flow[0].name.replace(/_/g, " ").toLowerCase()} ${flow[0].side}: not yet`;
    tone = "amber";
  }

  return {
    loading: its.isLoading,
    hasScan: !!last,
    spot: d?.spot ?? null,
    now: d?.now ?? null,
    wait: { short, tone, fib, flow, idle },
    scans: list.slice(0, 6).map((it) => ({
      id: it.id,
      at: it.createdAt,
      result: it.result,
      text: it.summary ?? it.details?.reason ?? "",
    })),
  };
}
