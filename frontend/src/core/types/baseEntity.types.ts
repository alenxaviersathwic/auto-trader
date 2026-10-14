export type EntityStatus = "ACTIVE" | "DELETED";

/**
 * BaseEntity shape inherited by all entities.
 * Directly matches backend BaseEntity fields (camelCase).
 */
export interface BaseEntity {
  id: number;
  createdAt: string;
  status: EntityStatus;
}
