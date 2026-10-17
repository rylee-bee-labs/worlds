/**
 * Query client factory — lives apart from QueryProvider.tsx so the
 * provider module exports only components (React Fast Refresh rule).
 */

import { QueryClient } from "@tanstack/react-query";

export function createDefaultQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,        // 30s — data is fresh
        gcTime: 5 * 60_000,       // 5min — keep in cache
        retry: 2,                  // retry twice on failure
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
    },
  });
}
