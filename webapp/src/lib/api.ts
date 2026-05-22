declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?: () => void; expand?: () => void } };
  }
}

let token = "";

export function setToken(t: string) {
  token = t;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(path, { ...init, headers });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json() as Promise<T>;
}

export async function createSession() {
  const initData = window.Telegram?.WebApp?.initData || "";
  return api<{ token: string; credits: number }>("/api/v1/webapp/session", {
    method: "POST",
    body: JSON.stringify({ initData }),
  });
}

export async function fetchMe() {
  return api<{ credits: number; username: string }>("/api/v1/me");
}

export async function fetchStyles() {
  return api<{ items: Array<{ key: string; name: string; is_trending?: boolean }> }>("/api/v1/styles");
}

export async function fetchTrending() {
  return api<{ items: Array<{ key: string; name: string }> }>("/api/v1/styles/trending");
}

export async function fetchGallery() {
  return api<{ items: unknown[] }>("/api/v1/gallery");
}

export async function fetchPackages() {
  return api<{ items: unknown[] }>("/api/v1/packages");
}

export async function createGeneration(prompt: string, image_b64: string, style_key?: string) {
  return api<{ job_id: string }>("/api/v1/generations", {
    method: "POST",
    body: JSON.stringify({ prompt, image_b64, style_key }),
  });
}

export async function pollJob(job_id: string) {
  return api<{ status: string; output_url?: string }>(`/api/v1/generations/${job_id}`);
}
