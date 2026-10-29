import { ApiError } from "../../../core/api/apiError";
import { queryClient } from "../../../core/query/queryClient";
import { suggestionApi } from "../api/suggestion.api";
import { suggestionQueryKeys } from "../queryKeys/suggestionQueryKeys";
import { LoopSnapshot } from "../types/suggestion.types";

const DEFAULT_GAP_SECONDS = 20;

/**
 * Client-driven suggestion loop. Lives at module level (not inside a component) so it keeps running
 * while you move between the Suggestion page and a card's detail page; it stops when the tab closes.
 *
 * One round = fetch today's cards, then call /iterate on every RUNNING session ONE BY ONE, then wait
 * loopGapSeconds. Stopped sessions drop out on the next round; the loop ends when none are RUNNING.
 */
class SuggestionLoopRunner {
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
    return queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all });
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

  /** Starts the loop if it is not already going. A new card session is picked up on the next round. */
  async run(): Promise<void> {
    if (this.snap.running) {
      this.wake?.(); // a card was just started: skip the rest of the gap and pick it up now
      return;
    }
    this.stopRequested = false;
    this.set({ running: true, lastError: null });
    try {
      while (!this.stopRequested) {
        const today = await suggestionApi.getTodayMasters();
        const queue = today.list.filter((m) => m.state === "RUNNING");
        if (queue.length === 0) break;
        this.set({ round: this.snap.round + 1 });
        for (const m of queue) {
          if (this.stopRequested) break;
          this.set({ currentMasterId: m.id, currentCode: m.underlyingCode });
          try {
            await suggestionApi.iterate(m.id);
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
    this.stopRequested = true;
    this.wake?.();
  }
}

export const suggestionLoopRunner = new SuggestionLoopRunner();
