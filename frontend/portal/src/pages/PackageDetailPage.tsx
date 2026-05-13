import { Alert, Button, Descriptions, Progress, Space, Steps, Typography } from "antd";
import { Download, ExternalLink, PackageCheck, ShieldCheck, TestTube2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { artifactChecksum, artifactMetadata, formatBytes, formatDate, shortHash, titleize } from "../lib/format";
import { useArtifacts, useBuild, useTraceability } from "../hooks/usePlatformQueries";

export function PackageDetailPage() {
  const { productId = "", buildId = "", artifactId = "" } = useParams();
  const product = decodeURIComponent(productId);
  const build = decodeURIComponent(buildId);
  const artifactRef = decodeURIComponent(artifactId);
  const buildQuery = useBuild(build, product);
  const artifactsQuery = useArtifacts(build, product);
  const traceabilityQuery = useTraceability(build, product);

  const detail = buildQuery.data;
  const artifact = artifactsQuery.data?.artifacts.find((item) => item.id === artifactRef || item.name === artifactRef);
  const metadata = artifact ? artifactMetadata(artifact) : {};
  const repositories = traceabilityQuery.data?.repositories.map((repo) => repo.repository) ?? [];
  const ciMetadata = detail?.ci_metadata ?? {};
  const testPassRate = inferPassRate(ciMetadata);

  if (artifactsQuery.isError || buildQuery.isError) {
    return <RetryEmptyState onRetry={() => void Promise.all([artifactsQuery.refetch(), buildQuery.refetch()])} />;
  }

  if (!artifact && !artifactsQuery.isLoading) {
    return <EmptyState title="Package not found." description="The artifact may have been removed or the URL is stale." />;
  }

  return (
    <>
      <PageHeader
        title={artifact?.name ?? "Package"}
        subtitle={detail ? `${detail.product_name} / build ${detail.build_id}` : "Package readiness and provenance"}
        breadcrumbs={[
          { label: "Products", to: "/products" },
          { label: product, to: `/products/${encodeURIComponent(product)}` },
          { label: build, to: `/builds/${encodeURIComponent(product)}/${encodeURIComponent(build)}` },
          { label: artifact?.name ?? "Package" }
        ]}
        actions={
          artifact ? (
            artifact.type === "oci_image" ? (
              <Typography.Text code copyable>
                docker pull {artifact.storage_uri}
              </Typography.Text>
            ) : (
              <Button href={artifact.storage_uri} target="_blank" icon={<Download size={16} />}>
                Download
              </Button>
            )
          ) : null
        }
      />

      {artifact ? (
        <section className="package-detail-grid">
          <div className="workspace-section">
            <Typography.Title level={2}>Package Provenance</Typography.Title>
            <Descriptions bordered size="small" column={1} className="description-table">
              <Descriptions.Item label="Name">{artifact.name}</Descriptions.Item>
              <Descriptions.Item label="Type">{titleize(artifact.type)}</Descriptions.Item>
              <Descriptions.Item label="Size">{formatBytes(artifact.size_bytes)}</Descriptions.Item>
              <Descriptions.Item label="Storage URI">
                <a href={artifact.storage_uri} target="_blank" rel="noreferrer">
                  {artifact.storage_uri} <ExternalLink size={12} />
                </a>
              </Descriptions.Item>
              <Descriptions.Item label="SHA-256">
                <Typography.Text code copyable={{ text: artifactChecksum(artifact) }}>
                  {shortHash(artifactChecksum(artifact), 24)}
                </Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="Source Repository">
                {String(metadata.repository ?? repositories[0] ?? "N/A")}
              </Descriptions.Item>
              <Descriptions.Item label="Build">
                <Link to={`/builds/${encodeURIComponent(product)}/${encodeURIComponent(build)}`}>{build}</Link>
              </Descriptions.Item>
            </Descriptions>
          </div>

          <div className="workspace-section">
            <Typography.Title level={2}>CI/CD & Testing</Typography.Title>
            <Steps
              direction="vertical"
              current={detail?.status === "released" ? 3 : detail?.status === "testing" ? 2 : 1}
              items={[
                { title: "Manifest stored", description: formatDate(detail?.created_at), icon: <PackageCheck size={18} /> },
                { title: "Traceability hydrated", description: detail?.traceability_incomplete ? "Pending enrichment" : "Complete" },
                { title: "QA validation", description: titleize(detail?.status), icon: <TestTube2 size={18} /> },
                { title: "Immutable release", description: detail?.released_at ? formatDate(detail.released_at) : "Not released", icon: <ShieldCheck size={18} /> }
              ]}
            />
            <div className="quality-strip">
              <div>
                <Typography.Text type="secondary">Pipeline Status</Typography.Text>
                <div>{detail ? <StatusBadge status={detail.status} /> : "N/A"}</div>
              </div>
              <div>
                <Typography.Text type="secondary">Test Pass Rate</Typography.Text>
                <Progress percent={testPassRate} size="small" status={testPassRate >= 90 ? "success" : "active"} />
              </div>
            </div>
            {Object.keys(ciMetadata).length ? (
              <pre className="code-block">{JSON.stringify(ciMetadata, null, 2)}</pre>
            ) : (
              <Alert type="info" showIcon message="No CI/CD metadata was attached for this package." />
            )}
          </div>

          <div className="workspace-section package-detail-grid__wide">
            <Typography.Title level={2}>Artifact Metadata</Typography.Title>
            {Object.keys(metadata).length ? (
              <pre className="code-block">{JSON.stringify(metadata, null, 2)}</pre>
            ) : (
              <Typography.Text type="secondary">No artifact-specific metadata recorded.</Typography.Text>
            )}
          </div>
        </section>
      ) : null}
    </>
  );
}

function inferPassRate(ciMetadata: Record<string, unknown>): number {
  const tests = ciMetadata.test_results;
  if (tests && typeof tests === "object") {
    const record = tests as Record<string, unknown>;
    const passed = Number(record.passed ?? 0);
    const failed = Number(record.failed ?? 0);
    const skipped = Number(record.skipped ?? 0);
    const total = passed + failed + skipped;
    return total ? Math.round((passed / total) * 100) : 0;
  }
  return 0;
}
