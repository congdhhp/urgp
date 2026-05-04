import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, App as AntApp } from "antd";
import "antd/dist/reset.css";
import "reactflow/dist/style.css";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15000
    }
  }
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
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
          colorBgLayout: "#f8fafc",
          colorBgContainer: "#ffffff",
          colorBorder: "#e2e8f0",
          colorTextSecondary: "#64748b",
          colorTextTertiary: "#94a3b8",
          fontSize: 14,
          lineHeight: 1.6,
          motionDurationMid: "0.15s",
          motionDurationSlow: "0.2s"
        },
        components: {
          Card: { borderRadiusLG: 10, paddingLG: 20 },
          Button: { borderRadius: 8, fontWeight: 500 },
          Table: {
            headerBg: "#f1f5f9",
            headerColor: "#64748b",
            headerSortHoverBg: "#e2e8f0",
            rowHoverBg: "#f8f9ff",
            borderRadius: 10,
            borderRadiusLG: 10
          },
          Layout: {
            headerBg: "rgba(255,255,255,0.88)",
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
          },
          Input: { borderRadius: 8 },
          Select: { borderRadius: 8 },
          Modal: { borderRadiusLG: 14 },
          Tabs: { inkBarColor: "#6366f1", itemActiveColor: "#6366f1", itemSelectedColor: "#6366f1" },
          Badge: { borderRadiusSM: 100 }
        }
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
);
