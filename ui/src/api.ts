export type CollectResult = {
  ok: boolean;
  grade: string;
  channel: string;
  source_tier: string;
  dimension: string;
  message: string;
  persona_id: string;
  data: Record<string, unknown> | null;
};

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `${path} ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => getJson<{ ok: boolean }>("/api/health"),
  doctor: (probe = false) => getJson<Record<string, unknown>>(`/api/doctor?probe=${probe}`),
  warehouse: () => getJson<Record<string, unknown>>("/api/warehouse"),
  sessions: () => getJson<{ sessions: Record<string, unknown> }>("/api/sessions"),
  neo4jProbe: () => getJson<Record<string, unknown>>("/api/neo4j/probe"),
  verify: () => getJson<Record<string, unknown>>("/api/verify"),
  collect: (body: {
    keyword: string;
    platform: string;
    dims: string;
    prefer_tier: string;
    depth: number;
  }) => postJson<CollectResult>("/api/collect", body),
  importNeo4j: (dry_run: boolean) =>
    postJson<Record<string, unknown>>("/api/import-neo4j", { dry_run }),
};
