import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { renderPortal } from "./test-utils";

vi.mock("./pages/ProductsPage", () => ({
  ProductsPage: () => <div>Product workspace loaded</div>
}));

describe("App routing", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("redirects unauthenticated users to the login screen", async () => {
    renderPortal(<App />, { authenticated: false, router: { initialEntries: ["/products"] } });

    expect(await screen.findByRole("heading", { name: /URGP Portal/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/API Key/i)).toBeInTheDocument();
  });

  it("renders protected product workspace for authenticated users", async () => {
    renderPortal(<App />, { router: { initialEntries: ["/products"] } });

    expect(await screen.findByText("Product workspace loaded")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /URGP products/i })).toBeInTheDocument();
  });
});
