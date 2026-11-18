import { ApiError } from "../../../core/api/apiError";
import { queryClient } from "../../../core/query/queryClient";
import { opportunitiesApi } from "../api/opportunities.api";
import { opportunitiesQueryKeys } from "../queryKeys/opportunitiesQueryKeys";
import { LoopSnapshot } from "../types/opportunities.types";

const DEFAULT_GAP_SECONDS = 20;
/** One loop per browser: every tab asks for this Web Lock and only the holder iterates (18 Nov 2026: two tabs each
 *  ran the loop, so every card was iterated twice and the backend answered 409 ITERATION_IN_PROGRESS). */
const LOOP_LOCK = "ordergrid-opportunity-loop";

/**
 * Client-driven opportunities loop. Lives at module level (not inside a component) so it keeps running
 * while you move between the Opportunities page and a card's detail page; it stops when the tab closes.
 *
 * One round = fetch today's cards, then call /iterate on every RUNNING session ONE BY ONE, then wait
 * loopGapSeconds. Stopped sessions drop out on the next round; the loop ends when none are RUNNING.
 * Errors (backend restart, network) never end the loop: it retries with a backoff until Stop is pressed.
 */
class OpportunityLoopRunner {
  private snap: LoopSnapshot = { running: false, round: 0, currentMasterId: null, currentCode: null, lastError: null };
  private listeners = new Set<() => void>();
  private stopRequested = false;
  private wake: (() => void) | null = null;

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getSnapshot = (): LoopSnapshot => this.snap;

  private set(patch: Partial<LoopSnapshot>) {
    this.snap = { ...this.snap, ...patch };
    this.listeners.forEach((fn) => fn());
  }

  private refresh() {
    return queryClient.invalidateQueries({ queryKey: opportunitiesQueryKeys.all });
  }

  private sleep(ms: number) {
    return new Promise<void>((resolve) => {
      const t = setTimeout(() => {
        this.wake = null;
        resolve();
      }, ms);
      this.wake = () => {
        clearTimeout(t);
        this.wake = null;
        resolve();
      };
    });
  }

  private waiting: AbortController | null = null;

  /** Starts the loop if it is not already going. A new card session is picked up on the next round. When another
   *  tab already runs the loop, this tab waits for the lock (and takes over if that tab closes). */
  async run(): Promise<void> {
    if (this.snap.running) {
      this.wake?.(); // a card was just started: skip the rest of the gap and pick it up now
      return;
    }
    if (this.waiting) return;
    const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
    if (!locks) return this.loop();
    this.waiting = new AbortController();
    try {
      await locks.request(LOOP_LOCK, { ifAvailable: true }, async (lock) => {
        if (lock) {
          this.waiting = null;
          await this.loop();
          return;
        }
        // another tab owns the loop: show it, then queue for the lock (taken over when that tab closes)
        this.set({ inOtherTab: true });
        await locks.request(LOOP_LOCK, { signal: this.waiting?.signal }, async () => {
          this.waiting = null;
          this.set({ inOtherTab: false });
          await this.loop();
        });
      });
    } catch {
      // aborted by stop(): nothing to do
    } finally {
      this.waiting = null;
      if (this.snap.inOtherTab) this.set({ inOtherTab: false });
    }
  }

  private async loop(): Promise<void> {
    this.stopRequested = false;
    this.set({ running: true, lastError: null });
    let failures = 0;
    try {
      while (!this.stopRequested) {
        let today;
        try {
          today = await opportunitiesApi.getTodayMasters();
          failures = 0;
        } catch (e) {
          // Backend restarting / network blip: keep the loop alive and retry (5s, 10s ... max 60s) instead of
          // ending it -- a dead loop silently stopped every card for hours (13 Nov 2026, 12:50-14:17).
          failures += 1;
          this.set({ lastError: `cards unavailable, retrying: ${e instanceof Error ? e.message : String(e)}` });
          await this.sleep(Math.min(60, 5 * failures) * 1000);
          continue;
        }
        if (this.snap.lastError?.startsWith("cards unavailable")) this.set({ lastError: null });
        const queue = today.list.filter((m) => m.state === "RUNNING");
        if (queue.length === 0) break;
        this.set({ round: this.snap.round + 1, backend: !!today.backendLoop });
        if (today.backendLoop) {
          // the backend iterates every card (opportunity_finder/job/scanner_job.py): just keep the page fresh
          await this.refresh();
          await this.sleep((queue[0].params?.loopGapSeconds ?? DEFAULT_GAP_SECONDS) * 1000);
          continue;
        }
        for (const m of queue) {
          if (this.stopRequested) break;
          this.set({ currentMasterId: m.id, currentCode: m.underlyingCode });
          try {
            await opportunitiesApi.iterate(m.id);
          } catch (e) {
            // 409 = another tab is iterating this card right now: skip it this round.
            if (!(e instanceof ApiError && e.statusCode === 409)) {
              this.set({ lastError: `${m.underlyingCode}: ${e instanceof Error ? e.message : String(e)}` });
            }
          }
          await this.refresh();
        }
        this.set({ currentMasterId: null, currentCode: null });
        if (this.stopRequested) break;
        await this.sleep((queue[0].params?.loopGapSeconds ?? DEFAULT_GAP_SECONDS) * 1000);
      }
    } catch (e) {
      this.set({ lastError: e instanceof Error ? e.message : String(e) });
    } finally {
      this.set({ running: false, currentMasterId: null, currentCode: null });
      await this.refresh();
    }
  }

  /** Stops after the card currently iterating finishes (an in-flight request is not aborted). */
  stop() {
    this.waiting?.abort();
    this.stopRequested = true;
    this.wake?.();
  }
}

export const opportunityLoopRunner = new OpportunityLoopRunner();

