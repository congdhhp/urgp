const STORAGE_KEY = "urgp_credentials";

interface StoredCredentials {
  apiKey: string;
  userId: string;
}

export const devCredentials: StoredCredentials = {
  apiKey: "dev-ingest-api-key-change-me",
  userId: "operator@example.com"
};

export function readStoredCredentials(): StoredCredentials {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { apiKey: "", userId: "" };
    return JSON.parse(raw) as StoredCredentials;
  } catch {
    return { apiKey: "", userId: "" };
  }
}

export function writeStoredCredentials(apiKey: string, userId: string): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ apiKey, userId }));
}

export function clearStoredCredentials(): void {
  localStorage.removeItem(STORAGE_KEY);
}
