/**
 * Standard API error thrown by httpClient when a request fails or backend returns an error envelope.
 */
export class ApiError extends Error {
  readonly statusCode: number;
  readonly error: unknown;

  constructor(statusCode: number, message: string, error: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.error = error;

    // Maintain prototype chain
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}
