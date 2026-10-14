import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/apiError";

/**
 * Global TanStack QueryClient with centralized error handling and defaults.
 */
export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        console.error(`[API Query Error ${error.statusCode}]: ${error.message}`, error.error);
      } else {
        console.error(`[Query Error]: ${error.message}`, error);
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error: Error) => {
      if (error instanceof ApiError) {
        console.error(`[API Mutation Error ${error.statusCode}]: ${error.message}`, error.error);
      } else {
        console.error(`[Mutation Error]: ${error.message}`, error);
      }
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      gcTime: 1000 * 60 * 5, // 5 minutes
      retry: (failureCount, error) => {
        // Do not retry 4xx client errors
        if (error instanceof ApiError && error.statusCode >= 400 && error.statusCode < 500) {
          return false;
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
