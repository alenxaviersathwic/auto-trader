/**
 * Universal API response envelope received from all backend endpoints.
 * Matches backend ApiResponse[T] exactly without casing mapping.
 */
export interface ApiResponse<T = unknown> {
  statusCode: number;
  data: T | null;
  message: string;
  error: unknown;
}
