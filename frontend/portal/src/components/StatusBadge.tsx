import { Tooltip } from "antd";

import type { BuildStatus } from "../types";

const PULSE_STATES = new Set(["ingesting", "hydrating", "testing"]);

const STATUS_LABELS: Record<string, string> = {
  ingesting: "Ingesting",
  hydrating: "Hydrating",
  completed: "Completed",
  testing: "Testing",
  released: "Released",
  deprecated: "Deprecated"
};

const STATUS_TOOLTIPS: Record<BuildStatus, string> = {
  ingesting: "Manifest accepted and waiting for processing.",
  hydrating: "Traceability hydration is in progress.",
  completed: "Build is complete and ready for QA intake.",
  testing: "QA validation is underway.",
  released: "Build is immutable and released.",
  deprecated: "Build was superseded or retired."
};

export function StatusBadge({ status }: { status: BuildStatus | string | null | undefined }) {
  const key = status ?? "";
  const label = STATUS_LABELS[key] ?? (key ? key.charAt(0).toUpperCase() + key.slice(1) : "N/A");
  const isPulsing = PULSE_STATES.has(key);

  const badge = (
    <span
      className={`status-badge status-badge--${key || "deprecated"}${isPulsing ? " status-badge--pulse" : ""}`}
    >
      <span className="status-badge__dot" />
      {label}
    </span>
  );

  if (!key || !(key in STATUS_TOOLTIPS)) {
    return badge;
  }

  return <Tooltip title={STATUS_TOOLTIPS[key as BuildStatus]}>{badge}</Tooltip>;
}
