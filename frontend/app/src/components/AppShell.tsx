import { useMemo, useState } from "react";
import { Avatar, Button, Dropdown, Input, Layout, Menu, Select, Space, Tooltip, Typography, theme } from "antd";
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
  const { token } = theme.useToken();
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
    icon: <item.icon size={18} />,
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
        width={252}
        collapsedWidth={76}
        collapsed={collapsed}
        className="app-sidebar"
        breakpoint="lg"
        onBreakpoint={setCollapsed}
      >
        <Link to="/products" className="app-brand" aria-label="URGP products">
          <span className="app-brand__mark">
            <ShieldCheck size={22} />
          </span>
          {!collapsed ? (
            <span>
              <strong>URGP</strong>
              <small>Release governance</small>
            </span>
          ) : null}
        </Link>
        <Menu mode="inline" selectedKeys={[selectedKey]} items={menuItems} className="app-sidebar__menu" />
        <div className="app-sidebar__footer">
          <Tooltip title={collapsed ? "API docs" : ""} placement="right">
            <Button href="http://localhost:8000/docs" target="_blank" icon={<PackageSearch size={16} />} block>
              {!collapsed ? "API Docs" : null}
            </Button>
          </Tooltip>
        </div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size={12}>
            <Button
              type="text"
              aria-label="Toggle navigation"
              icon={collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
              onClick={() => setCollapsed((value) => !value)}
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
                placeholder="Search build ID, commit hash, or issue ID"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onPressEnter={runSearch}
                suffix={
                  <Button type="text" size="small" aria-label="Search" icon={<Search size={16} />} onClick={runSearch} />
                }
              />
            </div>
          </Space>
          <Space size={16}>
            <Tooltip title="Notifications">
              <Link to="/settings" className="icon-link" aria-label="Notification settings">
                <Bell size={18} />
              </Link>
            </Tooltip>
            <Dropdown menu={{ items: accountMenu }} trigger={["click"]}>
              <button className="account-button" type="button">
                <Avatar style={{ background: token.colorPrimary }}>{(userId || "O").slice(0, 1).toUpperCase()}</Avatar>
                <span>
                  <Typography.Text strong>{userId || "Operator"}</Typography.Text>
                  <Typography.Text type="secondary">Portal session</Typography.Text>
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
