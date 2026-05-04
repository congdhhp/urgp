import { Tag, Tooltip } from "antd";

import { buildStatusTone, titleize } from "../lib/format";
import type { BuildStatus } from "../types";

const statusCopy: Record<BuildStatus, string> = {
  ingesting: "Manifest accepted and waiting for processing.",
  hydrating: "Traceability hydration is in progress.",
  completed: "Build is complete and ready for QA intake.",
  testing: "QA validation is underway.",
  released: "Build is immutable and released.",
  deprecated: "Build was superseded or retired."
};

export function StatusBadge({ status }: { status: BuildStatus | string | null | undefined }) {
  if (!status) {
    return <Tag>N/A</Tag>;
  }
  const content = <Tag color={buildStatusTone(status)}>{titleize(status)}</Tag>;
  return status in statusCopy ? <Tooltip title={statusCopy[status as BuildStatus]}>{content}</Tooltip> : content;
}
