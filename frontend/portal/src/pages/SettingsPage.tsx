import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Form, Input, Popconfirm, Select, Space, Switch, Table, Tabs, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Bell, Trash2 } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { createSubscription, deleteSubscription } from "../lib/api";
import { formatDateShort, titleize } from "../lib/format";
import { useAuth } from "../contexts/AuthContext";
import { useNotificationHistory, useProducts, useSubscriptions } from "../hooks/usePlatformQueries";
import type { NotificationChannel, NotificationHistoryItem, Subscription, SubscriptionCreateRequest } from "../types";

export function SettingsPage() {
  const { userId } = useAuth();
  const productsQuery = useProducts();
  const subscriptionsQuery = useSubscriptions();
  const historyQuery = useNotificationHistory({ limit: 50 });
  const queryClient = useQueryClient();
  const [form] = Form.useForm<SubscriptionCreateRequest>();
  const channel = Form.useWatch("channel", form) as NotificationChannel | undefined;

  const createMutation = useMutation({
    mutationFn: createSubscription,
    onSuccess: async () => {
      message.success("Subscription created.");
      form.resetFields();
      form.setFieldsValue({ channel: "email" });
      await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSubscription,
    onSuccess: async () => {
      message.success("Subscription removed.");
      await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    }
  });

  const subscriptionColumns: ColumnsType<Subscription> = [
    { title: "Product", dataIndex: "product_name" },
    { title: "Release", dataIndex: "release", render: (value) => value ?? "All releases" },
    { title: "Channel", dataIndex: "channel", render: titleize },
    {
      title: "Active",
      dataIndex: "active",
      render: (value) => <Switch checked={value} disabled />
    },
    { title: "Created", dataIndex: "created_at", render: formatDateShort },
    {
      title: "Actions",
      render: (_, subscription) => (
        <Popconfirm title="Remove this subscription?" onConfirm={() => deleteMutation.mutate(subscription.id)}>
          <Button danger icon={<Trash2 size={16} />} />
        </Popconfirm>
      )
    }
  ];

  const historyColumns: ColumnsType<NotificationHistoryItem> = [
    { title: "Build", dataIndex: "build_id" },
    { title: "Product", dataIndex: "product_name" },
    { title: "Event", dataIndex: "event_type", render: titleize },
    { title: "Channel", dataIndex: "channel", render: titleize },
    { title: "Status", dataIndex: "status", render: titleize },
    { title: "Attempts", dataIndex: "attempt_count" },
    { title: "Last Attempt", dataIndex: "last_attempt_at", render: formatDateShort }
  ];

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle={`Notification subscriptions for ${userId || "the current user"}.`}
        breadcrumbs={[{ label: "Settings" }]}
      />

      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "subscriptions",
            label: "Subscriptions",
            children: (
              <section className="settings-grid">
                <div className="workspace-section">
                  <Typography.Title level={2}>Create Subscription</Typography.Title>
                  <Form<SubscriptionCreateRequest>
                    form={form}
                    layout="vertical"
                    initialValues={{ channel: "email" }}
                    onFinish={(values) =>
                      createMutation.mutate({
                        ...values,
                        release: values.release || null,
                        webhook_url: values.channel === "webhook" ? values.webhook_url : null
                      })
                    }
                  >
                    <Form.Item label="Product" name="product_id" rules={[{ required: true }]}>
                      <Select
                        placeholder="Select product"
                        options={(productsQuery.data?.items ?? []).map((product) => ({
                          value: product.external_id,
                          label: product.name
                        }))}
                      />
                    </Form.Item>
                    <Form.Item label="Release train" name="release">
                      <Input placeholder="Optional release version" />
                    </Form.Item>
                    <Form.Item label="Channel" name="channel" rules={[{ required: true }]}>
                      <Select
                        options={[
                          { value: "email", label: "Email" },
                          { value: "webhook", label: "Webhook" }
                        ]}
                      />
                    </Form.Item>
                    {channel === "webhook" ? (
                      <Form.Item label="Webhook URL" name="webhook_url" rules={[{ required: true }, { type: "url" }]}>
                        <Input placeholder="https://hooks.example.com/urgp" />
                      </Form.Item>
                    ) : null}
                    <Space>
                      <Button type="primary" htmlType="submit" icon={<Bell size={16} />} loading={createMutation.isPending}>
                        Create
                      </Button>
                    </Space>
                  </Form>
                </div>
                <div className="workspace-section">
                  <Typography.Title level={2}>Current Subscriptions</Typography.Title>
                  <Table
                    rowKey="id"
                    columns={subscriptionColumns}
                    dataSource={subscriptionsQuery.data?.items ?? []}
                    loading={subscriptionsQuery.isLoading}
                    scroll={{ x: 900 }}
                  />
                </div>
              </section>
            )
          },
          {
            key: "history",
            label: "Delivery History",
            children: (
              <section className="workspace-section">
                <Table
                  rowKey="id"
                  columns={historyColumns}
                  dataSource={historyQuery.data?.items ?? []}
                  loading={historyQuery.isLoading}
                  scroll={{ x: 1000 }}
                />
              </section>
            )
          }
        ]}
      />
    </>
  );
}
