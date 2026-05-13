import { useMemo } from "react";
import { Alert, Timeline, Typography } from "antd";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, AlertTriangle, Box, CheckCircle2, GitBranch } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateShort, titleize } from "../lib/format";
import { useActivity } from "../hooks/usePlatformQueries";

export function ActivityPage() {
  const activityQuery = useActivity();
  const activity = activityQuery.data;

  const productChart = useMemo(
    () =>
      (activity?.products ?? []).map((product) => ({
        name: product.name,
        builds: product.build_count,
        releases: product.release_count
      })),
    [activity?.products]
  );

  const heatmap = useMemo(() => buildHeatmap(activity?.recent_builds ?? []), [activity?.recent_builds]);

  if (activityQuery.isError) {
    return <RetryEmptyState onRetry={() => void activityQuery.refetch()} />;
  }

  return (
    <>
      <PageHeader
        title="Activity"
        subtitle="Cross-product build monitoring, readiness signals, and recent lifecycle events."
        breadcrumbs={[{ label: "Activity" }]}
      />

      <section className="metric-grid">
        <MetricCard label="Products" value={activity?.totals.products ?? 0} note="Visible in P1" icon={Box} />
        <MetricCard label="Releases" value={activity?.totals.releases ?? 0} note="Tracked trains" icon={GitBranch} tone="green" />
        <MetricCard label="Released" value={activity?.totals.released_builds ?? 0} note="Immutable builds" icon={CheckCircle2} tone="amber" />
        <MetricCard label="Incomplete" value={activity?.totals.incomplete_builds ?? 0} note="Need hydration" icon={AlertTriangle} tone="red" />
      </section>

      {(activity?.totals.incomplete_builds ?? 0) > 0 ? (
        <Alert
          type="warning"
          showIcon
          className="content-alert"
          message={`${activity?.totals.incomplete_builds} builds still have incomplete traceability.`}
          description="Review hydrating builds or external integration failures before release approval."
        />
      ) : null}

      <section className="activity-grid">
        <div className="workspace-section">
          <Typography.Title level={2}>Live Build Feed</Typography.Title>
          {activity?.recent_builds.length ? (
            <Timeline
              items={activity.recent_builds.map((build) => ({
                color: build.status === "released" || build.status === "completed" ? "green" : "blue",
                children: (
                  <div className="timeline-item">
                    <Link to={`/builds/${encodeURIComponent(build.product_id)}/${encodeURIComponent(build.build_id)}`}>
                      {build.product_name} / {build.build_id}
                    </Link>
                    <StatusBadge status={build.status} />
                    <Typography.Text type="secondary">
                      {titleize(build.build_type)} / {formatDateShort(build.created_at)}
                    </Typography.Text>
                  </div>
                )
              }))}
            />
          ) : (
            <EmptyState title="No build activity recorded yet." />
          )}
        </div>

        <div className="workspace-section">
          <Typography.Title level={2}>Product Build Volume</Typography.Title>
          <div className="chart-panel">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={productChart}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="builds" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="releases" fill="#0f766e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="workspace-section activity-grid__wide">
          <Typography.Title level={2}>Recent Build Heatmap</Typography.Title>
          <div className="heatmap-grid">
            {heatmap.map((bucket) => (
              <div key={bucket.label} className="heatmap-cell" style={{ opacity: Math.max(0.25, Math.min(1, bucket.count / 4)) }}>
                <strong>{bucket.count}</strong>
                <span>{bucket.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="workspace-section activity-grid__wide">
          <Typography.Title level={2}>Build Trend</Typography.Title>
          <div className="chart-panel">
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={heatmap}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Area type="monotone" dataKey="count" fill="#4f46e5" stroke="#4f46e5" fillOpacity={0.18} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </>
  );
}

function buildHeatmap(builds: Array<{ created_at: string }>) {
  const buckets = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setDate(date.getDate() - (6 - index));
    const key = date.toISOString().slice(0, 10);
    return { key, label: date.toLocaleDateString(undefined, { month: "short", day: "2-digit" }), count: 0 };
  });
  for (const build of builds) {
    const key = new Date(build.created_at).toISOString().slice(0, 10);
    const bucket = buckets.find((item) => item.key === key);
    if (bucket) {
      bucket.count += 1;
    }
  }
  return buckets;
}
