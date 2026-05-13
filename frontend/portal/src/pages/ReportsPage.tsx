import { useMemo } from "react";
import { Table, Typography } from "antd";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { percent, titleize } from "../lib/format";
import { useBuilds, useProducts } from "../hooks/usePlatformQueries";

const statusColors = ["#2563eb", "#0f766e", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

export function ReportsPage() {
  const productsQuery = useProducts();
  const buildsQuery = useBuilds({ limit: 200 });
  const builds = buildsQuery.data?.items ?? [];

  const statusData = useMemo(() => summarize(builds.map((build) => build.status)), [builds]);
  const typeData = useMemo(() => summarize(builds.map((build) => build.build_type)), [builds]);
  const released = builds.filter((build) => build.status === "released").length;

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="P1 operational snapshots for release readiness, lifecycle mix, and product adoption."
        breadcrumbs={[{ label: "Reports" }]}
      />

      <section className="reports-grid">
        <div className="workspace-section">
          <Typography.Title level={2}>Lifecycle Mix</Typography.Title>
          {statusData.length ? <Donut data={statusData} /> : <EmptyState title="No build status data yet." />}
        </div>
        <div className="workspace-section">
          <Typography.Title level={2}>Build Types</Typography.Title>
          {typeData.length ? <Donut data={typeData} /> : <EmptyState title="No build type data yet." />}
        </div>
        <div className="workspace-section reports-grid__wide">
          <Typography.Title level={2}>Product Adoption</Typography.Title>
          <Table
            rowKey="external_id"
            loading={productsQuery.isLoading}
            dataSource={productsQuery.data?.items ?? []}
            columns={[
              { title: "Product", dataIndex: "name" },
              { title: "Releases", dataIndex: "release_count" },
              { title: "Builds", dataIndex: "build_count" },
              { title: "Last Build", dataIndex: "last_build_id", render: (value) => value ?? "N/A" },
              { title: "Last Status", dataIndex: "last_build_status", render: titleize }
            ]}
          />
        </div>
        <div className="workspace-section reports-grid__wide">
          <Typography.Title level={2}>MVP Readiness</Typography.Title>
          <div className="readiness-strip">
            <span>
              <strong>{builds.length}</strong>
              Total builds
            </span>
            <span>
              <strong>{released}</strong>
              Released builds
            </span>
            <span>
              <strong>{percent(released, builds.length)}</strong>
              Release ratio
            </span>
            <span>
              <strong>{productsQuery.data?.total ?? 0}</strong>
              Active catalog entries
            </span>
          </div>
        </div>
      </section>
    </>
  );
}

function summarize(values: string[]) {
  const map = new Map<string, number>();
  for (const value of values) {
    map.set(value, (map.get(value) ?? 0) + 1);
  }
  return Array.from(map.entries()).map(([name, value]) => ({ name: titleize(name), value }));
}

function Donut({ data }: { data: Array<{ name: string; value: number }> }) {
  return (
    <div className="chart-panel">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Tooltip />
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={56} outerRadius={92} paddingAngle={3}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={statusColors[index % statusColors.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
