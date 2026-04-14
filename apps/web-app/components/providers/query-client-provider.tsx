"use client";

import * as React from "react";
import {
  QueryClient,
  QueryClientProvider as TanStackQueryClientProvider,
} from "@tanstack/react-query";

/**
 * Wrapper cliente do `QueryClientProvider` do TanStack. Criado para que o
 * `RootLayout` (server component) possa instanciar um `QueryClient` uma
 * unica vez por sessao de navegacao no cliente, sem vazar o client para
 * o bundle de servidor.
 */
export function AppQueryClientProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );

  return (
    <TanStackQueryClientProvider client={client}>
      {children}
    </TanStackQueryClientProvider>
  );
}
