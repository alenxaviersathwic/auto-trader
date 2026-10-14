import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { ApiError } from "./apiError";
import { ApiResponse } from "../types/apiResponse.types";

/**
 * Global Axios HTTP Client.
 * Automatically unwraps ApiResponse envelopes and returns payload data directly.
 * Throws ApiError on non-2xx status codes or envelope errors.
 */
export const httpClient = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// Request interceptor
httpClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config;
  },
  (error: unknown) => {
    return Promise.reject(error);
  }
);

// Response interceptor unwrapping ApiResponse envelope
httpClient.interceptors.response.use(
  (response: AxiosResponse<ApiResponse<unknown>>) => {
    const envelope = response.data;

    // If response matches our standard envelope
    if (envelope && typeof envelope === "object" && "statusCode" in envelope) {
      if (envelope.statusCode >= 200 && envelope.statusCode < 300) {
        return envelope.data as any;
      }

      // If status code inside envelope represents an error
      throw new ApiError(
        envelope.statusCode,
        envelope.message || "Request failed",
        envelope.error
      );
    }

    // Direct data fallback (e.g., if response is raw binary or non-enveloped)
    return response.data as any;
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    if (error.response && error.response.data) {
      const envelope = error.response.data;
      if (typeof envelope === "object" && "statusCode" in envelope) {
        throw new ApiError(
          envelope.statusCode || error.response.status,
          envelope.message || error.message || "Request failed",
          envelope.error
        );
      }
      throw new ApiError(
        error.response.status,
        error.message || "HTTP Error",
        error.response.data
      );
    }

    // Network error or timeout without response
    throw new ApiError(
      0,
      error.message || "Network error. Please check your connection.",
      null
    );
  }
);
