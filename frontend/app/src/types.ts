export type BuildStatus = "ingesting" | "hydrating" | "completed" | "testing" | "released" | "deprecated";
export type BuildType = "nightly" | "weekly" | "rc" | "hotfix";
export type ArtifactType =
  | "eclipse_p2"
  | "oci_image"
  | "binary"
  | "npm_tarball"
  | "maven_jar"
  | "python_wheel"
  | "generic";
export type NotificationChannel = "email" | "webhook";

export interface ProductSummary {
  external_id: string;
  name: string;
  description?: string | null;
  release_count: number;
  build_count: number;
  last_build_id?: string | null;
  last_build_status?: BuildStatus | null;
  last_build_at?: string | null;
}

export interface ProductListResponse {
  items: ProductSummary[];
  total: number;
}

export interface ProductCreateRequest {
  external_id: string;
  name: string;
  description?: string | null;
  git_config?: Record<string, unknown> | null;
  issue_config?: Record<string, unknown> | null;
}

export interface ReleaseSummary {
  version: string;
  release_type?: string | null;
  status: string;
  build_count: number;
  last_build_id?: string | null;
  last_build_status?: BuildStatus | null;
  last_build_at?: string | null;
}

export interface ReleaseListResponse {
  product_id: string;
  product_name: string;
  items: ReleaseSummary[];
  total: number;
}

export interface ReleaseCreateRequest {
  version: string;
  release_type?: string | null;
  status: string;
}

export interface BuildSummary {
  id: string;
  build_id: string;
  product_id: string;
  product_name: string;
  release?: string | null;
  build_type: BuildType;
  status: BuildStatus;
  traceability_incomplete: boolean;
  created_at: string;
  updated_at: string;
  released_at?: string | null;
  cli_version?: string | null;
  signature?: string | null;
  artifact_count: number;
  commit_count: number;
  pull_request_count: number;
  issue_count: number;
  notification_count: number;
}

export interface BuildDetail extends BuildSummary {
  ci_metadata?: Record<string, unknown> | null;
}

export interface BuildListResponse {
  items: BuildSummary[];
  total: number;
}

export interface Artifact {
  id: string;
  name: string;
  type: ArtifactType;
  storage_uri: string;
  sha256?: string;
  sha256_checksum?: string;
  size_bytes?: number | null;
  metadata?: Record<string, unknown> | null;
  metadata_?: Record<string, unknown> | null;
}

export interface BuildArtifactsResponse {
  build_id: string;
  product_id: string;
  artifacts: Artifact[];
}

export interface PullRequest {
  external_id: string;
  title?: string | null;
  author?: string | null;
  source_branch?: string | null;
  target_branch?: string | null;
  merge_timestamp?: string | null;
  url?: string | null;
}

export interface Issue {
  external_id: string;
  tracker_type: string;
  title?: string | null;
  status?: string | null;
  priority?: string | null;
  assignee?: string | null;
  labels?: Record<string, unknown> | null;
  url?: string | null;
}

export interface CommitTraceability {
  repository: string;
  hash: string;
  branch?: string | null;
  author?: string | null;
  message?: string | null;
  committed_at?: string | null;
  pull_requests: PullRequest[];
  issues: Issue[];
}

export interface TraceabilityRepository {
  repository: string;
  commit_count: number;
  pull_request_count: number;
  issue_count: number;
  commits: CommitTraceability[];
}

export interface BuildTraceabilityResponse {
  build_id: string;
  product_id: string;
  status: BuildStatus;
  traceability_incomplete: boolean;
  commit_count: number;
  pull_request_count: number;
  issue_count: number;
  repositories: TraceabilityRepository[];
}

export interface BuildComparisonResponse {
  start_build_id: string;
  end_build_id: string;
  unique_commits: string[];
  unique_pull_requests: PullRequest[];
  unique_issues: Issue[];
}

export interface BuildVerificationArtifact {
  name: string;
  type: ArtifactType;
  sha256: string;
  integrity_status: "valid" | "invalid" | string;
  detail: string;
}

export interface BuildVerificationResponse {
  build_id: string;
  product_id: string;
  integrity_status: "valid" | "invalid" | string;
  traceability_incomplete: boolean;
  artifacts: BuildVerificationArtifact[];
  verification_timestamp: string;
}

export interface BuildSearchResponse {
  query: string;
  items: BuildSummary[];
  total: number;
}

export interface ActivityTotals {
  products: number;
  releases: number;
  builds: number;
  released_builds: number;
  incomplete_builds: number;
}

export interface ActivityResponse {
  generated_at: string;
  totals: ActivityTotals;
  recent_builds: BuildSummary[];
  products: ProductSummary[];
}

export interface Subscription {
  id: string;
  user_id: string;
  product_id: string;
  product_name: string;
  release?: string | null;
  channel: NotificationChannel;
  webhook_url?: string | null;
  active: boolean;
  created_at: string;
}

export interface SubscriptionListResponse {
  items: Subscription[];
  total: number;
}

export interface SubscriptionCreateRequest {
  product_id: string;
  release?: string | null;
  channel: NotificationChannel;
  webhook_url?: string | null;
}

export interface NotificationHistoryItem {
  id: string;
  subscription_id: string;
  manifest_id: string;
  build_id: string;
  product_id: string;
  product_name: string;
  release?: string | null;
  event_type: string;
  channel: NotificationChannel;
  recipient: string;
  status: "pending" | "sent" | "failed" | string;
  attempt_count: number;
  last_attempt_at?: string | null;
  sent_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationHistoryResponse {
  items: NotificationHistoryItem[];
  total: number;
}
