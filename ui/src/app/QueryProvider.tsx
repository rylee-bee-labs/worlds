/**
 * QueryProvider — TanStack Query context for Project Worlds.
 *
 * Manages server-state lifecycle: loading, stale, retry, refresh, unavailable, cached.
 */

import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createDefaultQueryClient } from "../data/queryClient";

interface QueryProviderProps {
  children: React.ReactNode;
  client?: QueryClient;
}

/**
 * Each provider instance owns its cache by default. A module-level
 * singleton would leak one screen mount's (or one Storybook story's)
 * server state into the next — cached fiction shown as current data.
 */
export function QueryProvider({ children, client }: QueryProviderProps) {
  const [queryClient] = useState(() => client ?? createDefaultQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
