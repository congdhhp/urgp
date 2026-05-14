import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuildDetailPage } from "./BuildDetailPage";
import { renderPortal } from "../test-utils";
import type { BuildArtifactsResponse, BuildDetail, BuildTraceabilityResponse } from "../types";

const mockUseBuild = vi.fn();
const mockUseArtifacts = vi.fn();
const mockUseTraceability = vi.fn();

vi.mock("../hooks/usePlatformQueries", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../hooks/usePlatformQueries")>();
  return {
    ...actual,
    useBuild: () => mockUseBuild(),
    useArtifacts: () => mockUseArtifacts(),
    useTraceability: () => mockUseTraceability()
  };
});

const build: BuildDetail = {
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
  released_at: null,
  cli_version: "0.1.0",
  signature: "manifest-signature",
  artifact_count: 1,
  commit_count: 1,
  pull_request_count: 1,
  issue_count: 1,
  notification_count: 0,
  ci_metadata: { job: "nightly" }
};

const artifacts: BuildArtifactsResponse = {
  build_id: build.build_id,
  product_id: build.product_id,
  artifacts: [
    {
      id: "artifact-1",
      name: "s32-update-site.zip",
      type: "eclipse_p2",
      storage_uri: "https://example.test/s32-update-site.zip",
      sha256_checksum: "abc123",
      size_bytes: 1024
    }
  ]
};

const traceability: BuildTraceabilityResponse = {
  build_id: build.build_id,
  product_id: build.product_id,
  status: "completed",
  traceability_incomplete: false,
  commit_count: 1,
  pull_request_count: 1,
  issue_count: 1,
  repositories: [
    {
      repository: "s32/ide",
      commit_count: 1,
      pull_request_count: 1,
      issue_count: 1,
      commits: [
        {
          repository: "s32/ide",
          hash: "abc123",
          branch: "main",
          author: "Release Engineer",
          message: "S32-123 Fix package metadata",
          committed_at: "2026-05-12T09:30:00Z",
          pull_requests: [{ external_id: "PR-42", title: "Fix package metadata" }],
          issues: [{ external_id: "S32-123", tracker_type: "jira", title: "Fix package metadata" }]
        }
      ]
    }
  ]
};

describe("BuildDetailPage", () => {
  beforeEach(() => {
    mockUseBuild.mockReturnValue({ data: build, isError: false, isLoading: false, refetch: vi.fn() });
    mockUseArtifacts.mockReturnValue({ data: artifacts, isError: false, isLoading: false, refetch: vi.fn() });
    mockUseTraceability.mockReturnValue({ data: traceability, isError: false, isLoading: false, refetch: vi.fn() });
  });

  it("renders build summary and traceability counts", async () => {
    renderPortal(
      <Routes>
        <Route path="/builds/:productId/:buildId" element={<BuildDetailPage />} />
      </Routes>,
      {
      router: { initialEntries: ["/builds/s32-design-studio/S32-2026.05.12"] }
      }
    );

    expect(await screen.findByRole("heading", { name: "S32-2026.05.12" })).toBeInTheDocument();
    expect(screen.getByText("S32 Design Studio / 2026.05")).toBeInTheDocument();
    expect(screen.getByText("Verify Integrity")).toBeInTheDocument();
    expect(screen.getByText("Packages (1)")).toBeInTheDocument();
    expect(screen.getByText("What's New (1)")).toBeInTheDocument();
    expect(screen.getByText(/HMAC-SHA256 verified/)).toBeInTheDocument();
  });
});
