import { useState } from "react";
import { Alert, Button, Form, Input, Space, Typography } from "antd";
import { KeyRound, Rocket, ShieldCheck } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { devCredentials } from "../lib/storage";

interface LoginFormValues {
  apiKey: string;
  userId: string;
}

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const [form] = Form.useForm<LoginFormValues>();
  const [usedDev, setUsedDev] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/products" replace />;
  }

  function submit(values: LoginFormValues) {
    login(values.apiKey, values.userId);
    navigate("/products");
  }

  function useDevCredentials() {
    form.setFieldsValue(devCredentials);
    setUsedDev(true);
  }

  return (
    <main className="login-screen">
      <section className="login-panel">
        <div className="login-panel__brand">
          <span>
            <ShieldCheck size={28} />
          </span>
          <div>
            <Typography.Title level={1}>URGP Portal</Typography.Title>
            <Typography.Text>Universal Release Governance Platform</Typography.Text>
          </div>
        </div>

        <Alert
          type="info"
          showIcon
          message="Use the same API key as the local backend."
          description="For local Docker development, the default key is available from .env.docker."
        />

        <Form<LoginFormValues>
          form={form}
          layout="vertical"
          initialValues={{ userId: devCredentials.userId }}
          onFinish={submit}
          requiredMark={false}
        >
          <Form.Item
            label="API Key"
            name="apiKey"
            rules={[{ required: true, message: "API key is required" }]}
          >
            <Input.Password prefix={<KeyRound size={16} />} placeholder="Paste X-API-Key" autoComplete="off" />
          </Form.Item>
          <Form.Item
            label="User or email"
            name="userId"
            rules={[{ required: true, message: "User id is required for notification subscriptions" }]}
          >
            <Input placeholder="operator@example.com" autoComplete="email" />
          </Form.Item>
          {usedDev ? <Alert type="success" showIcon message="Local development credentials loaded." /> : null}
          <Space wrap>
            <Button type="primary" htmlType="submit" icon={<Rocket size={16} />}>
              Enter Portal
            </Button>
            <Button onClick={useDevCredentials}>Use Local Dev Key</Button>
          </Space>
        </Form>
      </section>
    </main>
  );
}
