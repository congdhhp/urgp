import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductsPage } from "./ProductsPage";
import { renderPortal } from "../test-utils";
import type { ActivityResponse, BuildListResponse, ProductListResponse } from "../types";

const mockUseProducts = vi.fn();
const mockUseActivity = vi.fn();
const mockUseBuilds = vi.fn();

vi.mock("../hooks/usePlatformQueries", () => ({
  useProducts: () => mockUseProducts(),
  useActivity: () => mockUseActivity(),
  useBuilds: () => mockUseBuilds()
}));

const products: ProductListResponse = {
  total: 2,
  items: [
    {
      external_id: "s32-design-studio",
      name: "S32 Design Studio",
      description: "Automotive IDE release train",
      release_count: 2,
      build_count: 12,
      last_build_id: "S32-2026.05.12",
      last_build_status: "completed"
    },
    {
      external_id: "gateway-fw",
      name: "Gateway Firmware",
      description: "Embedded gateway release line",
      release_count: 1,
      build_count: 4,
      last_build_id: "GW-44",
      last_build_status: "testing"
    }
  ]
};

const activity: ActivityResponse = {
  generated_at: "2026-05-13T00:00:00Z",
  totals: {
    products: 2,
    releases: 3,
    builds: 16,
    released_builds: 8,
    incomplete_builds: 1
  },
  recent_builds: [],
  products: products.items
};

const builds: BuildListResponse = {
  total: 1,
  items: [
    {
      id: "manifest-1",
      build_id: "S32-2026.05.12",
      product_id: "s32-design-studio",
      product_name: "S32 Design Studio",
      release: "2026.05",
      build_type: "nightly",
      status: "completed",
      traceability_incomplete: false,
      created_at: "2026-05-12T10:00:00Z",
      updated_at: "2026-05-12T10:05:00Z",
      artifact_count: 3,
      commit_count: 14,
      pull_request_count: 4,
      issue_count: 5,
      notification_count: 2
    }
  ]
};

describe("ProductsPage", () => {
  beforeEach(() => {
    mockUseProducts.mockReturnValue({ data: products, isError: false, isLoading: false, refetch: vi.fn() });
    mockUseActivity.mockReturnValue({ data: activity, isError: false, isLoading: false, refetch: vi.fn() });
    mockUseBuilds.mockReturnValue({ data: builds, isError: false, isLoading: false, refetch: vi.fn() });
  });

  it("shows product metrics, catalog cards, and recent builds", async () => {
    renderPortal(<ProductsPage />, { router: { initialEntries: ["/products"] } });

    expect(await screen.findByRole("heading", { name: "Products" })).toBeInTheDocument();
    expect(screen.getAllByText("S32 Design Studio").length).toBeGreaterThan(0);
    expect(screen.getByText("Gateway Firmware")).toBeInTheDocument();
    expect(screen.getAllByText("S32-2026.05.12").length).toBeGreaterThan(0);
    expect(screen.getByText("14 commits / 5 issues")).toBeInTheDocument();
  });

  it("filters the product catalog by name", async () => {
    renderPortal(<ProductsPage />, { router: { initialEntries: ["/products"] } });

    fireEvent.change(screen.getByPlaceholderText("Filter products"), { target: { value: "gateway" } });

    const catalog = screen.getByRole("heading", { name: "Product Catalog" }).closest("section");
    expect(catalog).not.toBeNull();
    expect(within(catalog as HTMLElement).getByText("Gateway Firmware")).toBeInTheDocument();
    expect(within(catalog as HTMLElement).queryByText("S32 Design Studio")).not.toBeInTheDocument();
  });
});
