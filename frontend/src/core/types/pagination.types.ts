/**
 * PageResult generic structure returned in data on search endpoints.
 */
export interface PageResult<T> {
  list: T[];
  page: number;
  limit: number;
  totalPages: number;
  totalItems: number;
}
