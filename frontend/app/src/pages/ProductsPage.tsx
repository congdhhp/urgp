import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, Input, Modal, Row, Space, Table, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Activity, Box, CheckCircle2, Clock3, Plus, Search, ShieldAlert } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { EmptyState, RetryEmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { createProduct } from "../lib/api";
import { formatDateShort, percent } from "../lib/format";
import { useActivity, useBuilds, useProducts } from "../hooks/usePlatformQueries";
import type { BuildSummary, ProductCreateRequest, ProductSummary } from "../types";

export function ProductsPage() {
  const productsQuery = useProducts();
  const activityQuery = useActivity();
  const buildsQuery = useBuilds({ limit: 8 });
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<ProductCreateRequest>();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const createMutation = useMutation({
    mutationFn: createProduct,
    onSuccess: async (product) => {
      message.success(`Product ${product.name} is ready.`);
      setModalOpen(false);
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ["products"] });
      await queryClient.invalidateQueries({ queryKey: ["activity"] });
      navigate(`/products/${encodeURIComponent(product.external_id)}`);
    }
  });

  const products = productsQuery.data?.items ?? [];
  const totals = activityQuery.data?.totals;
  const filteredProducts = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return products;
    }
    return products.filter((product) =>
      [product.name, product.external_id, product.description ?? ""].some((value) => value.toLowerCase().includes(needle))
    );
  }, [products, search]);

  const releasedRate = totals ? percent(totals.released_builds, totals.builds) : 0;

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
    { title: "Status", dataIndex: "status", render: (value) => <StatusBadge status={value} /> },
    { title: "Changes", render: (_, build) => `${build.commit_count} commits / ${build.issue_count} issues` },
    { title: "Created", dataIndex: "created_at", render: formatDateShort }
  ];

  if (productsQuery.isError) {
    return <RetryEmptyState onRetry={() => void productsQuery.refetch()} />;
  }

  return (
    <>
      <PageHeader
        title="Products"
        subtitle="A single catalog for release trains, build history, traceability, and package readiness."
        actions={
          <Button type="primary" icon={<Plus size={16} />} onClick={() => setModalOpen(true)}>
            New Product
          </Button>
        }
      />

      <section className="metric-grid">
        <MetricCard label="Products" value={totals?.products ?? products.length} note="Onboarded lines" icon={Box} />
        <MetricCard label="Builds" value={totals?.builds ?? 0} note="Manifest records" icon={Activity} tone="green" />
        <MetricCard label="Released" value={`${releasedRate}%`} note={`${totals?.released_builds ?? 0} immutable`} icon={CheckCircle2} tone="amber" />
        <MetricCard label="Incomplete" value={totals?.incomplete_builds ?? 0} note="Need hydration review" icon={ShieldAlert} tone="red" />
      </section>

      {!products.length && !productsQuery.isLoading ? (
        <Alert
          type="warning"
          showIcon
          className="content-alert"
          message="No products are available yet."
          description="Run the database seed command or create a product from this page to start using the portal."
        />
      ) : null}

      <section className="workspace-section">
        <div className="section-toolbar">
          <div>
            <Typography.Title level={2}>Product Catalog</Typography.Title>
            <Typography.Text type="secondary">Browse product workspaces and drill into releases.</Typography.Text>
          </div>
          <Input
            allowClear
            prefix={<Search size={16} />}
            placeholder="Filter products"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="section-toolbar__search"
          />
        </div>

        {filteredProducts.length ? (
          <Row gutter={[16, 16]}>
            {filteredProducts.map((product) => (
              <Col xs={24} md={12} xl={8} key={product.external_id}>
                <ProductCard product={product} />
              </Col>
            ))}
          </Row>
        ) : (
          <EmptyState title="No products match the current search." />
        )}
      </section>

      <section className="workspace-section">
        <div className="section-toolbar">
          <div>
            <Typography.Title level={2}>Recent Builds</Typography.Title>
            <Typography.Text type="secondary">Latest manifest activity across all products.</Typography.Text>
          </div>
          <Clock3 size={20} />
        </div>
        <Table
          rowKey={(build) => `${build.product_id}-${build.build_id}`}
          dataSource={buildsQuery.data?.items ?? []}
          columns={columns}
          loading={buildsQuery.isLoading}
          pagination={false}
          scroll={{ x: 900 }}
        />
      </section>

      <Modal
        open={modalOpen}
        title="Create Product"
        okText="Create"
        confirmLoading={createMutation.isPending}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form<ProductCreateRequest> form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Form.Item label="External ID" name="external_id" rules={[{ required: true }]}>
            <Input placeholder="s32-design-studio" />
          </Form.Item>
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="S32 Design Studio" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea rows={3} placeholder="Short product description" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

function ProductCard({ product }: { product: ProductSummary }) {
  return (
    <Card className="catalog-card" hoverable>
      <Space direction="vertical" size={14} className="full-width">
        <div className="catalog-card__top">
          <span className="catalog-card__icon">
            <Box size={20} />
          </span>
          {product.last_build_status ? <StatusBadge status={product.last_build_status} /> : null}
        </div>
        <div>
          <Typography.Title level={3}>{product.name}</Typography.Title>
          <Typography.Text type="secondary">{product.description ?? product.external_id}</Typography.Text>
        </div>
        <div className="catalog-card__stats">
          <span>
            <strong>{product.release_count}</strong>
            Releases
          </span>
          <span>
            <strong>{product.build_count}</strong>
            Builds
          </span>
          <span>
            <strong>{product.last_build_id ?? "N/A"}</strong>
            Last build
          </span>
        </div>
        <Button type="primary" block>
          <Link to={`/products/${encodeURIComponent(product.external_id)}`}>Open Releases</Link>
        </Button>
      </Space>
    </Card>
  );
}
