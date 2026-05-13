import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

function chunkName(id: string): string | undefined {
  const normalized = id.replaceAll("\\", "/");
  if (!normalized.includes("/node_modules/")) {
    return undefined;
  }

  if (/\/node_modules\/(react|react-dom|react-router|react-router-dom)\//.test(normalized)) {
    return "react";
  }
  if (normalized.includes("/node_modules/@remix-run/router/")) {
    return "react";
  }
  if (normalized.includes("/node_modules/@tanstack/") || normalized.includes("/node_modules/axios/")) {
    return "query";
  }
  if (normalized.includes("/node_modules/reactflow/")) {
    return "reactflow";
  }
  if (normalized.includes("/node_modules/recharts/") || normalized.includes("/node_modules/d3-")) {
    return "recharts";
  }

  const antdComponent = normalized.match(/\/node_modules\/antd\/es\/([^/]+)/)?.[1];
  if (antdComponent) {
    return `antd-${antdComponent.replace(/[^a-z0-9_-]/gi, "-")}`;
  }
  const antPackage = normalized.match(/\/node_modules\/(@ant-design\/[^/]+)/)?.[1];
  if (antPackage) {
    return antPackage.replace("@", "").replace("/", "-");
  }
  const rcPackage = normalized.match(/\/node_modules\/(rc-[^/]+)/)?.[1];
  if (rcPackage) {
    return rcPackage;
  }
  if (normalized.includes("/node_modules/antd/")) {
    return "antd";
  }

  return "vendor";
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: chunkName
      }
    }
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000"
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts"
  }
});
