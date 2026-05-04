import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { getBuilds, searchByCommit, searchByIssue } from "../lib/api";
import { formatDateShort, titleize } from "../lib/format";
import type { BuildSummary } from "../types";

export function SearchPage() {
  const [params] = useSearchParams();
  const query = params.get("q") ?? "";
  const type = params.get("type") ?? "build";

  const searchQuery = useQuery({
    queryKey: ["global-search", type, query],
    enabled: Boolean(query),
    queryFn: async () => {
      if (type === "commit") {
        return searchByCommit(query);
      }
      if (type === "issue") {
        return searchByIssue(query);
      }
      const builds = await getBuilds({ limit: 200 });
      const needle = query.toLowerCase();
      return {
        query,
        total: builds.items.filter((build) => build.build_id.toLowerCase().includes(needle)).length,
        items: builds.items.filter((build) => build.build_id.toLowerCase().includes(needle))
      };
    }
  });

  const rows = useMemo(() => searchQuery.data?.items ?? [], [searchQuery.data?.items]);

  const columns: ColumnsType<BuildSummary> = [
    {
      title: "Build",
      dataIndex: "build_id",
      render: (_, build) => (
        <Link to={`/builds/${encodeURIComponent(build.product_id)}/${encodeURIComponent(build.build_id)}`}>
          {build.build_id}
        </Link>
      )
    },
    { title: "Product", dataIndex: "product_name" },
    { title: "Release", dataIndex: "release", render: (value) => value ?? "Unassigned" },
    { title: "Type", dataIndex: "build_type", render: titleize },
    { title: "Status", dataIndex: "status", render: (value) => <StatusBadge status={value} /> },
    { title: "Created", dataIndex: "created_at", render: formatDateShort }
  ];

  if (searchQuery.isError) {
    return <RetryEmptyState onRetry={() => void searchQuery.refetch()} />;
  }

  return (
    <>
      <PageHeader
        title="Search"
        subtitle={query ? `Results for ${type}: ${query}` : "Search by build ID, commit hash, or issue ID."}
        breadcrumbs={[{ label: "Search" }]}
      />

      {!query ? (
        <EmptyState title="Enter a search query from the header." />
      ) : (
        <section className="workspace-section">
          {type === "build" ? (
            <Alert
              type="info"
              showIcon
              className="content-alert"
              message="Build ID search scans the latest 200 build manifests in P1."
            />
          ) : null}
          <Typography.Title level={2}>{searchQuery.data?.total ?? 0} matches</Typography.Title>
          <Table rowKey="id" columns={columns} dataSource={rows} loading={searchQuery.isLoading} scroll={{ x: 900 }} />
        </section>
      )}
    </>
  );
}
