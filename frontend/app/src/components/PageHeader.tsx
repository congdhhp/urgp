import { Breadcrumb } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, breadcrumbs = [], actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      {breadcrumbs.length ? (
        <Breadcrumb
          className="page-header__crumbs"
          items={breadcrumbs.map((item) => ({
            title: item.to ? <Link to={item.to}>{item.label}</Link> : item.label
          }))}
        />
      ) : null}
      <div className="page-header__main">
        <div>
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {actions ? <div className="page-header__actions">{actions}</div> : null}
      </div>
    </header>
  );
}
