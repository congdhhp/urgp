import { useQuery } from "@tanstack/react-query";

import {
  getActivity,
  getArtifacts,
  getBuild,
  getBuilds,
  getNotificationHistory,
  getProducts,
  getReleases,
  getSubscriptions,
  getTraceability,
  type BuildListParams
} from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export function useProducts() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["products"],
    queryFn: getProducts,
    enabled: isAuthenticated
  });
}

export function useActivity() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["activity"],
    queryFn: getActivity,
    enabled: isAuthenticated,
    refetchInterval: 30000
  });
}

export function useReleases(productId?: string) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["releases", productId],
    queryFn: () => getReleases(productId as string),
    enabled: isAuthenticated && Boolean(productId)
  });
}

export function useBuilds(params: BuildListParams = {}, enabled = true) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["builds", params],
    queryFn: () => getBuilds(params),
    enabled: isAuthenticated && enabled
  });
}

export function useBuild(buildId?: string, productId?: string) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["build", productId, buildId],
    queryFn: () => getBuild(buildId as string, productId),
    enabled: isAuthenticated && Boolean(buildId)
  });
}

export function useArtifacts(buildId?: string, productId?: string) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["artifacts", productId, buildId],
    queryFn: () => getArtifacts(buildId as string, productId),
    enabled: isAuthenticated && Boolean(buildId)
  });
}

export function useTraceability(buildId?: string, productId?: string) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["traceability", productId, buildId],
    queryFn: () => getTraceability(buildId as string, productId),
    enabled: isAuthenticated && Boolean(buildId)
  });
}

export function useSubscriptions() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["subscriptions"],
    queryFn: getSubscriptions,
    enabled: isAuthenticated
  });
}

export function useNotificationHistory(params: { limit?: number } = { limit: 20 }) {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["notification-history", params],
    queryFn: () => getNotificationHistory(params),
    enabled: isAuthenticated
  });
}
