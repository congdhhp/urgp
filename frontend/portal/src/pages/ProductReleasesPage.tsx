import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Col, Form, Input, Modal, Row, Select, Space, Typography, message } from "antd";
import { CalendarClock, GitBranch, PackageCheck, Plus, Rocket } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { createRelease } from "../lib/api";
import { formatDateShort, titleize } from "../lib/format";
import { useBuilds, useProducts, useReleases } from "../hooks/usePlatformQueries";
import type { ReleaseCreateRequest, ReleaseSummary } from "../types";

export function ProductReleasesPage() {
  const { productId = "" } = useParams();
  const decodedProductId = decodeURIComponent(productId);
  const productsQuery = useProducts();
  const releasesQuery = useReleases(decodedProductId);
  const buildsQuery = useBuilds({ product_id: decodedProductId, limit: 200 }, Boolean(decodedProductId));
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<ReleaseCreateRequest>();
  const queryClient = useQueryClient();

  const product = productsQuery.data?.items.find((item) => item.external_id === decodedProductId);
  const releases = releasesQuery.data?.items ?? [];
  const activeReleases = releases.filter((release) => release.status === "active").length;

  const buildTypes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const build of buildsQuery.data?.items ?? []) {
      counts.set(build.build_type, (counts.get(build.build_type) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([type, count]) => `${titleize(type)} ${count}`)
      .join(" / ");
  }, [buildsQuery.data?.items]);

  const createMutation = useMutation({
    mutationFn: (payload: ReleaseCreateRequest) => createRelease(decodedProductId, payload),
    onSuccess: async () => {
      message.success("Release created.");
      setModalOpen(false);
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ["releases", decodedProductId] });
      await queryClient.invalidateQueries({ queryKey: ["products"] });
    }
  });

  if (releasesQuery.isError) {
    return <RetryEmptyState onRetry={() => void releasesQuery.refetch()} />;
  }

  return (
    <>
      <PageHeader
        title={product?.name ?? decodedProductId}
        subtitle="Release train overview with lifecycle status and build density."
        breadcrumbs={[{ label: "Products", to: "/products" }, { label: product?.name ?? decodedProductId }]}
        actions={
          <Button type="primary" icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>
            New Release
          </Button>
        }
      />

      <section className="metric-grid">
        <MetricCard label="Releases" value={releases.length} note={`${activeReleases} active`} icon={GitBranch} />
        <MetricCard label="Builds" value={buildsQuery.data?.total ?? 0} note={buildTypes || "No builds yet"} icon={PackageCheck} tone="green" />
        <MetricCard label="Latest Build" value={product?.last_build_id ?? "N/A"} note={product?.last_build_at ? formatDateShort(product.last_build_at) : "No activity"} icon={CalendarClock} tone="amber" />
        <MetricCard label="Last Status" value={product?.last_build_status ? titleize(product.last_build_status) : "N/A"} note="Lifecycle badge" icon={Rocket} tone="violet" />
      </section>

      <section className="workspace-section">
        <div className="section-toolbar">
          <div>
            <Typography.Title level={2}>Release Trains</Typography.Title>
            <Typography.Text type="secondary">Choose a release to inspect build manifests and compare snapshots.</Typography.Text>
          </div>
        </div>

        {releasesQuery.isLoading ? (
          <Row gutter={[16, 16]}>
            {[1, 2, 3].map((item) => (
              <Col xs={24} md={12} xl={8} key={item}>
                <Card loading />
              </Col>
            ))}
          </Row>
        ) : releases.length ? (
          <Row gutter={[16, 16]}>
            {releases.map((release) => (
              <Col xs={24} md={12} xl={8} key={release.version}>
                <ReleaseCard release={release} productId={decodedProductId} />
              </Col>
            ))}
          </Row>
        ) : (
          <EmptyState
            title="No release trains yet."
            description="Create the first release train for this product."
            action={
              <Button type="primary" onClick={() => setModalOpen(true)}>
                Create Release
              </Button>
            }
          />
        )}
      </section>

      <Modal
        open={modalOpen}
        title="Create Release"
        okText="Create"
        confirmLoading={createMutation.isPending}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form<ReleaseCreateRequest>
          form={form}
          layout="vertical"
          initialValues={{ status: "active" }}
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item label="Version" name="version" rules={[{ required: true }]}>
            <Input placeholder="3.6.8 RFP" />
          </Form.Item>
          <Form.Item label="Release type" name="release_type">
            <Input placeholder="RFP, RC, Hotfix" />
          </Form.Item>
          <Form.Item label="Status" name="status">
            <Select
              options={[
                { value: "active", label: "Active" },
                { value: "planned", label: "Planned" },
                { value: "closed", label: "Closed" }
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function ReleaseCard({ release, productId }: { release: ReleaseSummary; productId: string }) {
  return (
    <Card className="catalog-card" hoverable>
      <Space direction="vertical" size={14} className="full-width">
        <div className="catalog-card__top">
          <span className="catalog-card__icon">
            <GitBranch size={20} />
          </span>
          {release.last_build_status ? <StatusBadge status={release.last_build_status} /> : null}
        </div>
        <div>
          <Typography.Title level={3}>{release.version}</Typography.Title>
          <Typography.Text type="secondary">
            {release.release_type ?? "General"} / {titleize(release.status)}
          </Typography.Text>
        </div>
        <div className="catalog-card__stats">
          <span>
            <strong>{release.build_count}</strong>
            Builds
          </span>
          <span>
            <strong>{release.last_build_id ?? "N/A"}</strong>
            Latest
          </span>
          <span>
            <strong>{release.last_build_at ? formatDateShort(release.last_build_at) : "N/A"}</strong>
            Updated
          </span>
        </div>
        <Button type="primary" block>
          <Link to={`/products/${encodeURIComponent(productId)}/releases/${encodeURIComponent(release.version)}`}>
            Open Builds
          </Link>
        </Button>
      </Space>
    </Card>
  );
}
