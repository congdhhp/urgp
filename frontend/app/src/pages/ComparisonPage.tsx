import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Select, Space, Table, Tabs, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Download, FileJson, GitCommit, Play } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { compareBuilds } from "../lib/api";
import { comparisonToCsv, diffArtifacts } from "../lib/compareUtils";
import { artifactChecksum, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuilds, useProducts } from "../hooks/usePlatformQueries";
import type { Artifact, Issue, PullRequest } from "../types";

export function ComparisonPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [product, setProduct] = useState(searchParams.get("product") ?? "");
  const [start, setStart] = useState(searchParams.get("start") ?? "");
  const [end, setEnd] = useState(searchParams.get("end") ?? "");

  const productsQuery = useProducts();
  const buildsQuery = useBuilds({ product_id: product || undefined, limit: 200 }, Boolean(product));
  const startArtifactsQuery = useArtifacts(start, product);
  const endArtifactsQuery = useArtifacts(end, product);

  const comparisonQuery = useQuery({
    queryKey: ["comparison", product, start, end],
    queryFn: () => compareBuilds(start, end, product),
    enabled: Boolean(product && start && end)
  });

  const artifactDiff = useMemo(
    () => diffArtifacts(startArtifactsQuery.data?.artifacts ?? [], endArtifactsQuery.data?.artifacts ?? []),
    [endArtifactsQuery.data?.artifacts, startArtifactsQuery.data?.artifacts]
  );

  useEffect(() => {
    if (!product || !start || !end) {
      return;
    }
    setSearchParams({ product, start, end });
  }, [end, product, setSearchParams, start]);

  const buildOptions = (buildsQuery.data?.items ?? []).map((build) => ({
    value: build.build_id,
    label: `${build.build_id} / ${build.release ?? "no release"} / ${titleize(build.status)}`
  }));

  function exportJson() {
    if (!comparisonQuery.data) {
      return;
    }
    downloadText(
      `urgp-comparison-${start}-${end}.json`,
      JSON.stringify({ comparison: comparisonQuery.data, packages: artifactDiff }, null, 2),
      "application/json"
    );
  }

  function exportCsv() {
    if (!comparisonQuery.data) {
      return;
    }
    downloadText(`urgp-comparison-${start}-${end}.csv`, comparisonToCsv(comparisonQuery.data, artifactDiff), "text/csv");
  }

  return (
    <>
      <PageHeader
        title="Build Comparison"
        subtitle="Compare two build manifests across issues, pull requests, commits, and package checksums."
        breadcrumbs={[{ label: "Comparisons" }]}
        actions={
          <Space wrap>
            <Button icon={<FileJson size={16} />} disabled={!comparisonQuery.data} onClick={exportJson}>
              Export JSON
            </Button>
            <Button icon={<Download size={16} />} disabled={!comparisonQuery.data} onClick={exportCsv}>
              Export CSV
            </Button>
          </Space>
        }
      />

      <section className="workspace-section compare-picker">
        <Select
          placeholder="Select product"
          value={product || undefined}
          onChange={(value) => {
            setProduct(value);
            setStart("");
            setEnd("");
          }}
          options={(productsQuery.data?.items ?? []).map((item) => ({ value: item.external_id, label: item.name }))}
        />
        <Select
          showSearch
          placeholder="Start build"
          value={start || undefined}
          onChange={setStart}
          options={buildOptions}
          optionFilterProp="label"
          disabled={!product}
        />
        <Select
          showSearch
          placeholder="End build"
          value={end || undefined}
          onChange={setEnd}
          options={buildOptions}
          optionFilterProp="label"
          disabled={!product}
        />
        <Button
          type="primary"
          icon={<Play size={16} />}
          loading={comparisonQuery.isFetching}
          disabled={!product || !start || !end}
          onClick={() => {
            void comparisonQuery.refetch();
            message.info("Comparison refreshed.");
          }}
        >
          Compare
        </Button>
      </section>

      {comparisonQuery.data ? (
        <Tabs
          className="workspace-tabs"
          items={[
            {
              key: "issues",
              label: `Issues (${comparisonQuery.data.unique_issues.length})`,
              children: <IssueDiffTable issues={comparisonQuery.data.unique_issues} />
            },
            {
              key: "pull-requests",
              label: `Pull Requests (${comparisonQuery.data.unique_pull_requests.length})`,
              children: <PullRequestDiffTable pullRequests={comparisonQuery.data.unique_pull_requests} />
            },
            {
              key: "packages",
              label: `Packages (${artifactDiff.added.length + artifactDiff.removed.length + artifactDiff.changed.length})`,
              children: <PackageDiffTable diff={artifactDiff} />
            },
            {
              key: "commits",
              label: `Commits (${comparisonQuery.data.unique_commits.length})`,
              children: <CommitDiffTable commits={comparisonQuery.data.unique_commits} />
            }
          ]}
        />
      ) : (
        <EmptyState title="Select a product and two builds to compare." />
      )}
    </>
  );
}

function IssueDiffTable({ issues }: { issues: Issue[] }) {
  const columns: ColumnsType<Issue> = [
    { title: "Issue", dataIndex: "external_id" },
    { title: "Title", dataIndex: "title", render: (value) => value ?? "Untitled" },
    { title: "Priority", dataIndex: "priority", render: (value) => value ?? "N/A" },
    { title: "Status", dataIndex: "status", render: (value) => value ?? "N/A" }
  ];
  return <Table rowKey={(issue) => `${issue.tracker_type}-${issue.external_id}`} columns={columns} dataSource={issues} />;
}

function PullRequestDiffTable({ pullRequests }: { pullRequests: PullRequest[] }) {
  const columns: ColumnsType<PullRequest> = [
    { title: "PR", dataIndex: "external_id" },
    { title: "Title", dataIndex: "title", render: (value) => value ?? "Untitled" },
    { title: "Author", dataIndex: "author", render: (value) => value ?? "N/A" },
    { title: "Branch", render: (_, pr) => `${pr.source_branch ?? "unknown"} -> ${pr.target_branch ?? "unknown"}` }
  ];
  return <Table rowKey="external_id" columns={columns} dataSource={pullRequests} />;
}

function PackageDiffTable({ diff }: { diff: ReturnType<typeof diffArtifacts> }) {
  const rows = [
    ...diff.added.map((artifact) => ({ kind: "Added", artifact })),
    ...diff.removed.map((artifact) => ({ kind: "Removed", artifact })),
    ...diff.changed.map(({ after }) => ({ kind: "Changed", artifact: after }))
  ];
  const columns: ColumnsType<{ kind: string; artifact: Artifact }> = [
    { title: "Diff", dataIndex: "kind" },
    { title: "Package", render: (_, row) => row.artifact.name },
    { title: "Type", render: (_, row) => titleize(row.artifact.type) },
    {
      title: "Checksum",
      render: (_, row) => (
        <Typography.Text code copyable={{ text: artifactChecksum(row.artifact) }}>
          {shortHash(artifactChecksum(row.artifact), 16)}
        </Typography.Text>
      )
    }
  ];
  return <Table rowKey={(row) => `${row.kind}-${row.artifact.id}`} columns={columns} dataSource={rows} />;
}

function CommitDiffTable({ commits }: { commits: string[] }) {
  const rows = commits.map((commit) => ({ commit }));
  return (
    <Table
      rowKey="commit"
      dataSource={rows}
      columns={[
        {
          title: "Commit Hash",
          dataIndex: "commit",
          render: (value) => (
            <Space>
              <GitCommit size={16} />
              <Typography.Text code copyable>
                {value}
              </Typography.Text>
            </Space>
          )
        }
      ]}
    />
  );
}

function downloadText(filename: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
