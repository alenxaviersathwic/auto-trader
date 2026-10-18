import { UserSearchFilter } from "../types/users.types";

/**
 * Query Key Factory for Users Module.
 * Ensures consistent key caching and granular invalidation.
 */
export const userQueryKeys = {
  all: ["users"] as const,
  lists: () => [...userQueryKeys.all, "list"] as const,
  list: (filter: UserSearchFilter) => [...userQueryKeys.lists(), filter] as const,
  details: () => [...userQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...userQueryKeys.details(), id] as const,
  default: () => [...userQueryKeys.all, "default"] as const,
  redirectUrl: (id: number) => [...userQueryKeys.all, "redirectUrl", id] as const,
};
