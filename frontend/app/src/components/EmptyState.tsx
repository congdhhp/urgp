import { Button, Empty } from "antd";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state-panel">
      <Empty description={description ?? title} image={Empty.PRESENTED_IMAGE_SIMPLE}>
        {action ? action : null}
      </Empty>
    </div>
  );
}

export function RetryEmptyState({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      title="Data could not be loaded"
      description="Check the API key, backend status, then try again."
      action={
        <Button type="primary" onClick={onRetry}>
          Retry
        </Button>
      }
    />
  );
}
