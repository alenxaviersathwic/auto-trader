import { EntityStatus } from "./baseEntity.types";

export interface DateFilter {
  from: string | null;
  to: string | null;
}

/**
 * BaseFilter contract for all list/search queries.
 * Sent in POST /api/v1/<resource>/search bodies.
 */
export interface BaseFilter {
  page: number; // zero-based
  limit: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  status?: EntityStatus;
  query?: string;
  dateFilter?: DateFilter | null;
}
