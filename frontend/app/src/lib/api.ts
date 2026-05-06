import axios from "axios";

import type {
  ActivityResponse,
  BuildArtifactsResponse,
  BuildComparisonResponse,
  BuildDetail,
  BuildListResponse,
  BuildSearchResponse,
  BuildTraceabilityResponse,
  BuildVerificationResponse,
  NotificationHistoryResponse,
  ProductCreateRequest,
  ProductListResponse,
  ProductSummary,
  ReleaseCreateRequest,
  ReleaseListResponse,
  ReleaseSummary,
  SubscriptionCreateRequest,
  SubscriptionListResponse,
  BuildStatus
} from "../types";
import { readStoredCredentials } from "./storage";

export type { BuildListResponse };

export interface BuildListParams {
  product_id?: string;
  release?: string;
  status?: BuildStatus;
  traceability_incomplete?: boolean;
  limit?: number;
  offset?: number;
}

const BASE_URL = "/api/v1";

function headers(): Record<string, string> {
  const { apiKey, userId } = readStoredCredentials();
  return {
    "X-API-Key": apiKey,
    "X-User-Id": userId
  };
}

const api = axios.create({ baseURL: BASE_URL });
api.interceptors.request.use((config) => {
  config.headers = { ...config.headers, ...headers() } as typeof config.headers;
  return config;
});

export async function getActivity(): Promise<ActivityResponse> {
  return (await api.get<ActivityResponse>("/activity")).data;
}

export async function getProducts(): Promise<ProductListResponse> {
  return (await api.get<ProductListResponse>("/products")).data;
}

export async function createProduct(payload: ProductCreateRequest): Promise<ProductSummary> {
  return (await api.post<ProductSummary>("/products", payload)).data;
}

export async function getReleases(productId: string): Promise<ReleaseListResponse> {
  return (await api.get<ReleaseListResponse>(`/products/${encodeURIComponent(productId)}/releases`)).data;
}

export async function createRelease(productId: string, payload: ReleaseCreateRequest): Promise<ReleaseSummary> {
  return (await api.post<ReleaseSummary>(`/products/${encodeURIComponent(productId)}/releases`, payload)).data;
}

export async function getBuilds(params: BuildListParams = {}): Promise<BuildListResponse> {
  return (await api.get<BuildListResponse>("/builds", { params })).data;
}

export async function getBuild(buildRef: string, productId?: string): Promise<BuildDetail> {
  return (await api.get<BuildDetail>(`/builds/${encodeURIComponent(buildRef)}`, { params: productId ? { product_id: productId } : {} })).data;
}

export async function getArtifacts(buildRef: string, productId?: string): Promise<BuildArtifactsResponse> {
  return (await api.get<BuildArtifactsResponse>(`/builds/${encodeURIComponent(buildRef)}/artifacts`, { params: productId ? { product_id: productId } : {} })).data;
}

export async function getTraceability(buildRef: string, productId?: string): Promise<BuildTraceabilityResponse> {
  return (await api.get<BuildTraceabilityResponse>(`/builds/${encodeURIComponent(buildRef)}/traceability`, { params: productId ? { product_id: productId } : {} })).data;
}

export async function verifyBuild(buildRef: string, productId?: string): Promise<BuildVerificationResponse> {
  return (await api.post<BuildVerificationResponse>(`/builds/${encodeURIComponent(buildRef)}/verify`, null, { params: productId ? { product_id: productId } : {} })).data;
}

export async function transitionBuildStatus(buildRef: string, productId: string, targetStatus: BuildStatus): Promise<BuildDetail> {
  return (
    await api.patch<BuildDetail>(
      `/builds/${encodeURIComponent(buildRef)}/status`,
      { status: targetStatus },
      { params: productId ? { product_id: productId } : {} }
    )
  ).data;
}

export async function compareBuilds(start: string, end: string, productId?: string): Promise<BuildComparisonResponse> {
  return (await api.get<BuildComparisonResponse>("/builds/compare", { params: { start, end, ...(productId ? { product_id: productId } : {}) } })).data;
}

export async function searchByCommit(commitHash: string): Promise<BuildSearchResponse> {
  return (await api.get<BuildSearchResponse>(`/builds/search/by-commit/${encodeURIComponent(commitHash)}`)).data;
}

export async function searchByIssue(issueId: string): Promise<BuildSearchResponse> {
  return (await api.get<BuildSearchResponse>(`/builds/search/by-issue/${encodeURIComponent(issueId)}`)).data;
}

export async function getSubscriptions(): Promise<SubscriptionListResponse> {
  return (await api.get<SubscriptionListResponse>("/notifications/subscriptions")).data;
}

export async function createSubscription(payload: SubscriptionCreateRequest): Promise<void> {
  await api.post("/notifications/subscriptions", payload);
}

export async function deleteSubscription(id: string): Promise<void> {
  await api.delete(`/notifications/subscriptions/${id}`);
}

export async function getNotificationHistory(params: { limit?: number } = {}): Promise<NotificationHistoryResponse> {
  return (await api.get<NotificationHistoryResponse>("/notifications/history", { params })).data;
}
