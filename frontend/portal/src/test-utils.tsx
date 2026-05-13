import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { render, type RenderOptions } from "@testing-library/react";

import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";

interface PortalRenderOptions extends Omit<RenderOptions, "wrapper"> {
  router?: MemoryRouterProps;
  authenticated?: boolean;
}

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0
      },
      mutations: {
        retry: false
      }
    }
  });
}

export function renderPortal(ui: ReactElement, options: PortalRenderOptions = {}) {
  const { router, authenticated = true, ...renderOptions } = options;

  if (authenticated) {
    localStorage.setItem(
      "urgp_credentials",
      JSON.stringify({ apiKey: "test-api-key", userId: "operator@example.com" })
    );
  } else {
    localStorage.removeItem("urgp_credentials");
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={createTestQueryClient()}>
          <AuthProvider>
            <MemoryRouter {...router}>{children}</MemoryRouter>
          </AuthProvider>
        </QueryClientProvider>
      </ThemeProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}
