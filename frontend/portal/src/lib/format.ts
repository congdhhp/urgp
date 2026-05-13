import dayjs from "dayjs";

import type { Artifact } from "../types";

export function formatDateShort(date?: string | null): string {
  if (!date) return "—";
  return dayjs(date).format("MMM D, YYYY");
}

export function formatDate(date?: string | null): string {
  if (!date) return "—";
  return dayjs(date).format("MMM D, YYYY HH:mm");
}

export function titleize(str?: string | null): string {
  if (!str) return "—";
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function shortHash(hash?: string | null, length = 8): string {
  if (!hash) return "—";
  return hash.slice(0, length);
}

export function formatBytes(bytes?: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export function artifactChecksum(artifact: Artifact): string {
  return artifact.sha256 ?? artifact.sha256_checksum ?? "";
}

export function artifactMetadata(artifact: Artifact): Record<string, unknown> {
  return artifact.metadata ?? artifact.metadata_ ?? {};
}

export function percent(value?: number | null, total?: number | null): string {
  if (value == null || total == null || total === 0) return "0%";
  return `${Math.round((value / total) * 100)}%`;
}
