import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, App as AntApp, theme as antTheme } from "antd";
import "antd/dist/reset.css";
import "reactflow/dist/style.css";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider, useTheme } from "./contexts/ThemeContext";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15000
    }
  }
});

const SHARED_TOKENS = {
  colorPrimary: "#6366f1",
  colorSuccess: "#22c55e",
  colorWarning: "#f59e0b",
  colorError: "#ef4444",
  colorInfo: "#6366f1",
  borderRadius: 10,
  borderRadiusLG: 14,
  borderRadiusSM: 6,
  fontFamily:
    "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontSize: 14,
  lineHeight: 1.6,
  motionDurationMid: "0.15s",
  motionDurationSlow: "0.2s"
} as const;

const SHARED_COMPONENTS = {
  Card: { borderRadiusLG: 10, paddingLG: 20 },
  Button: { borderRadius: 8, fontWeight: 500 },
  Table: {
    headerSortHoverBg: "transparent",
    borderRadius: 10,
    borderRadiusLG: 10
  },
  Input: { borderRadius: 8 },
  Select: { borderRadius: 8 },
  Modal: { borderRadiusLG: 14 },
  Tabs: { inkBarColor: "#6366f1", itemActiveColor: "#6366f1", itemSelectedColor: "#6366f1" },
  Badge: { borderRadiusSM: 100 }
} as const;

function ThemedConfigProvider({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          ...SHARED_TOKENS,
          colorBgLayout: isDark ? "#0c0c0f" : "#f8fafc",
          colorBgContainer: isDark ? "#111114" : "#ffffff",
          colorBorder: isDark ? "#27272a" : "#e2e8f0",
          colorTextSecondary: isDark ? "#a1a1aa" : "#64748b",
          colorTextTertiary: isDark ? "#71717a" : "#94a3b8"
        },
        components: {
          ...SHARED_COMPONENTS,
          Table: {
            ...SHARED_COMPONENTS.Table,
            headerBg: isDark ? "#18181b" : "#f1f5f9",
            headerColor: isDark ? "#a1a1aa" : "#64748b",
            rowHoverBg: isDark ? "#1c1c20" : "#f8f9ff"
          },
          Layout: {
            headerBg: isDark ? "rgba(17,17,20,0.88)" : "rgba(255,255,255,0.88)",
            siderBg: "#09090b"
          },
          Menu: {
            darkItemBg: "transparent",
            darkItemHoverBg: "rgba(255,255,255,0.06)",
            darkItemSelectedBg: "rgba(99,102,241,0.13)",
            darkItemColor: "#a1a1aa",
            darkItemSelectedColor: "#a5b4fc",
            itemHeight: 36,
            iconSize: 16
          }
        }
      }}
    >
      <AntApp>{children}</AntApp>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ThemedConfigProvider>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </ThemedConfigProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
);
