import { useMemo, useState } from "react";
import { Button, DatePicker, Input, Select, Segmented, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import { GitCompareArrows, Search } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateShort, titleize } from "../lib/format";
import { useBuilds, useProducts } from "../hooks/usePlatformQueries";
import type { BuildStatus, BuildSummary, BuildType } from "../types";

const { RangePicker } = DatePicker;

const buildTypeOptions: Array<"all" | BuildType> = ["all", "nightly", "weekly", "rc", "hotfix"];
const statusOptions: BuildStatus[] = ["ingesting", "hydrating", "completed", "testing", "released", "deprecated"];

export function ReleaseBuildsPage() {
  const { productId = "", releaseId = "" } = useParams();
  const product = decodeURIComponent(productId);
  const release = decodeURIComponent(releaseId);
  const productsQuery = useProducts();
  const buildsQuery = useBuilds({ product_id: product, release, limit: 200 }, Boolean(product && release));
  const navigate = useNavigate();

  const [buildType, setBuildType] = useState<"all" | BuildType>("all");
  const [status, setStatus] = useState<BuildStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [selectedRows, setSelectedRows] = useState<BuildSummary[]>([]);

  const productName = productsQuery.data?.items.find((item) => item.external_id === product)?.name ?? product;
  const builds = buildsQuery.data?.items ?? [];

  const filteredBuilds = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return builds.filter((build) => {
      if (buildType !== "all" && build.build_type !== buildType) {
        return false;
      }
      if (status !== "all" && build.status !== status) {
        return false;
      }
      if (needle && ![build.build_id, build.product_name, build.release ?? ""].some((value) => value.toLowerCase().includes(needle))) {
        return false;
      }
      if (range?.[0] && new Date(build.created_at) < range[0].startOf("day").toDate()) {
        return false;
      }
      if (range?.[1] && new Date(build.created_at) > range[1].endOf("day").toDate()) {
        return false;
      }
      return true;
    });
  }, [buildType, builds, range, search, status]);

  const columns: ColumnsType<BuildSummary> = [
    {
      title: "Build ID",
      dataIndex: "build_id",
      fixed: "left",
      render: (_, build) => (
        <Link to={`/builds/${encodeURIComponent(build.product_id)}/${encodeURIComponent(build.build_id)}`}>
          {build.build_id}
        </Link>
      )
    },
    { title: "Type", dataIndex: "build_type", render: titleize },
    { title: "Status", dataIndex: "status", render: (value) => <StatusBadge status={value} /> },
    {
      title: "Traceability",
      render: (_, build) =>
        build.traceability_incomplete ? (
          <Typography.Text type="warning">Incomplete</Typography.Text>
        ) : (
          <Typography.Text type="success">Complete</Typography.Text>
        )
    },
    { title: "Commits", dataIndex: "commit_count", sorter: (a, b) => a.commit_count - b.commit_count },
    { title: "Issues", dataIndex: "issue_count", sorter: (a, b) => a.issue_count - b.issue_count },
    { title: "Packages", dataIndex: "artifact_count", sorter: (a, b) => a.artifact_count - b.artifact_count },
    { title: "Notifications", dataIndex: "notification_count" },
    { title: "Created", dataIndex: "created_at", render: formatDateShort, sorter: (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at) }
  ];

  function compareSelected() {
    if (selectedRows.length !== 2) {
      return;
    }
    const sorted = [...selectedRows].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
    navigate(
      `/compare?product=${encodeURIComponent(product)}&start=${encodeURIComponent(sorted[0].build_id)}&end=${encodeURIComponent(
        sorted[1].build_id
      )}`
    );
  }

  if (buildsQuery.isError) {
    return <RetryEmptyState onRetry={() => void buildsQuery.refetch()} />;
  }

  return (
    <>
      <PageHeader
        title={release}
        subtitle={`Build manifests for ${productName}. Filter by lifecycle, type, and creation date.`}
        breadcrumbs={[
          { label: "Products", to: "/products" },
          { label: productName, to: `/products/${encodeURIComponent(product)}` },
          { label: release }
        ]}
        actions={
          <Button icon={<GitCompareArrows size={16} />} disabled={selectedRows.length !== 2} onClick={compareSelected}>
            Compare Selected
          </Button>
        }
      />

      <section className="workspace-section">
        <div className="filters-bar">
          <Segmented
            value={buildType}
            onChange={(value) => setBuildType(value as "all" | BuildType)}
            options={buildTypeOptions.map((value) => ({ value, label: titleize(value) }))}
          />
          <Select
            value={status}
            onChange={setStatus}
            className="filter-control"
            options={[{ value: "all", label: "All statuses" }, ...statusOptions.map((value) => ({ value, label: titleize(value) }))]}
          />
          <RangePicker value={range} onChange={(value) => setRange(value)} />
          <Input
            allowClear
            className="filters-bar__search"
            prefix={<Search size={16} />}
            placeholder="Find build ID"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        {builds.length ? (
          <Table
            rowKey={(build) => build.id}
            dataSource={filteredBuilds}
            columns={columns}
            loading={buildsQuery.isLoading}
            scroll={{ x: 1100 }}
            rowSelection={{
              type: "checkbox",
              selectedRowKeys: selectedRows.map((row) => row.id),
              onChange: (_, rows) => setSelectedRows(rows.slice(-2)),
              getCheckboxProps: (record) => ({ disabled: selectedRows.length >= 2 && !selectedRows.some((row) => row.id === record.id) })
            }}
            onRow={(record) => ({
              onDoubleClick: () => navigate(`/builds/${encodeURIComponent(record.product_id)}/${encodeURIComponent(record.build_id)}`)
            })}
          />
        ) : (
          <EmptyState title="No builds in this release yet." description="Push a build manifest through the CLI or Event Gateway." />
        )}
      </section>

      <Space className="table-help" wrap>
        <Typography.Text type="secondary">Double-click a row to open build details.</Typography.Text>
        <Typography.Text type="secondary">Select exactly two builds to compare issues, PRs, commits, and packages.</Typography.Text>
      </Space>
    </>
  );
}
