import { useMemo, useState } from "react";
import { Avatar, Button, Dropdown, Input, Layout, Menu, Select, Space, Tooltip, Typography } from "antd";
import type { MenuProps } from "antd";
import {
  Activity,
  BarChart3,
  Bell,
  Box,
  ChevronLeft,
  ChevronRight,
  GitCompareArrows,
  LogOut,
  PackageSearch,
  Search,
  Settings,
  ShieldCheck
} from "lucide-react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

const { Content, Header, Sider } = Layout;

const navItems = [
  { key: "/products", label: "Products", icon: Box },
  { key: "/activity", label: "Activity", icon: Activity },
  { key: "/compare", label: "Comparisons", icon: GitCompareArrows },
  { key: "/reports", label: "Reports", icon: BarChart3 },
  { key: "/settings", label: "Settings", icon: Settings }
];

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("build");
  const location = useLocation();
  const navigate = useNavigate();
  const { userId, logout } = useAuth();

  const selectedKey = useMemo(() => {
    const match = navItems.find((item) => location.pathname.startsWith(item.key));
    return match?.key ?? "/products";
  }, [location.pathname]);

  const menuItems: MenuProps["items"] = navItems.map((item) => ({
    key: item.key,
    icon: <item.icon size={16} />,
    label: <Link to={item.key}>{item.label}</Link>
  }));

  const accountMenu: MenuProps["items"] = [
    {
      key: "settings",
      icon: <Settings size={16} />,
      label: <Link to="/settings">Notification settings</Link>
    },
    {
      key: "logout",
      icon: <LogOut size={16} />,
      label: "Sign out",
      onClick: () => {
        logout();
        navigate("/login");
      }
    }
  ];

  function runSearch() {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    navigate(`/search?type=${encodeURIComponent(searchType)}&q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <Layout className="app-shell">
      <Sider
        width={240}
        collapsedWidth={68}
        collapsed={collapsed}
        className="app-sidebar"
        breakpoint="lg"
        onBreakpoint={setCollapsed}
        theme="dark"
      >
        <Link to="/products" className="app-brand" aria-label="URGP products">
          <span className="app-brand__mark">
            <ShieldCheck size={18} />
          </span>
          {!collapsed ? (
            <span>
              <strong>URGP</strong>
              <small>Release governance</small>
            </span>
          ) : null}
        </Link>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[selectedKey]}
          items={menuItems}
          className="app-sidebar__menu"
        />
        <div className="app-sidebar__footer">
          <Tooltip title={collapsed ? "API docs" : ""} placement="right">
            <Button href="http://localhost:8000/docs" target="_blank" icon={<PackageSearch size={15} />} block>
              {!collapsed ? "API Docs" : null}
            </Button>
          </Tooltip>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size={10}>
            <Button
              type="text"
              aria-label="Toggle navigation"
              icon={collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
              onClick={() => setCollapsed((value) => !value)}
              style={{ color: "var(--text-muted)" }}
            />
            <div className="app-header__search">
              <Select
                value={searchType}
                onChange={setSearchType}
                options={[
                  { value: "build", label: "Build" },
                  { value: "commit", label: "Commit" },
                  { value: "issue", label: "Issue" }
                ]}
                popupMatchSelectWidth={false}
              />
              <Input
                aria-label="Search builds commits or issues"
                placeholder="Search build ID, commit hash, or issue…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onPressEnter={runSearch}
                suffix={
                  <Button type="text" size="small" aria-label="Search" icon={<Search size={14} />} onClick={runSearch} />
                }
              />
            </div>
          </Space>
          <Space size={12}>
            <Tooltip title="Notification settings">
              <Link to="/settings" className="icon-link" aria-label="Notification settings">
                <Bell size={16} />
              </Link>
            </Tooltip>
            <Dropdown menu={{ items: accountMenu }} trigger={["click"]}>
              <button className="account-button" type="button">
                <Avatar
                  size={28}
                  style={{
                    background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    flexShrink: 0
                  }}
                >
                  {(userId || "O").slice(0, 1).toUpperCase()}
                </Avatar>
                <span>
                  <Typography.Text strong style={{ fontSize: "0.83rem" }}>
                    {userId || "Operator"}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: "0.72rem" }}>
                    Portal session
                  </Typography.Text>
                </span>
              </button>
            </Dropdown>
          </Space>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
