import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CollectResult } from "./api";

type Page = "settings" | "aiqicha" | "status";
type ResultTab = "basic" | "holders" | "invest" | "branch" | "raw";

function asRows(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter((x) => x && typeof x === "object") as Record<string, unknown>[];
  return [];
}

function firstInfo(data: Record<string, unknown> | null): Record<string, unknown> {
  if (!data) return {};
  const info = data.enterprise_info;
  if (Array.isArray(info) && info[0] && typeof info[0] === "object") return info[0] as Record<string, unknown>;
  if (info && typeof info === "object") return info as Record<string, unknown>;
  return data;
}

function SimpleTable({ rows, columns }: { rows: Record<string, unknown>[]; columns: string[] }) {
  if (!rows.length) return <p className="muted">无数据</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("aiqicha");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [doctor, setDoctor] = useState<Record<string, unknown> | null>(null);
  const [warehouse, setWarehouse] = useState<Record<string, unknown> | null>(null);
  const [verify, setVerify] = useState<Record<string, unknown> | null>(null);
  const [neo4jProbe, setNeo4jProbe] = useState<Record<string, unknown> | null>(null);

  const [keyword, setKeyword] = useState("");
  const [platform, setPlatform] = useState("aiqicha");
  const [dims, setDims] = useState("registry,equity");
  const [preferTier, setPreferTier] = useState("");
  const [result, setResult] = useState<CollectResult | null>(null);
  const [tab, setTab] = useState<ResultTab>("basic");

  const refreshSettings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [d, w, v, n] = await Promise.all([
        api.doctor(false),
        api.warehouse(),
        api.verify(),
        api.neo4jProbe(),
      ]);
      setDoctor(d);
      setWarehouse(w);
      setVerify(v);
      setNeo4jProbe(n);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshSettings();
  }, [refreshSettings]);

  const info = useMemo(() => firstInfo(result?.data ?? null), [result]);
  const holders = useMemo(
    () =>
      asRows(result?.data?.partner)
        .concat(asRows(result?.data?.stockholder))
        .concat(asRows(result?.data?.holder)),
    [result],
  );
  const invests = useMemo(
    () => asRows(result?.data?.invest).concat(asRows(result?.data?.holds)),
    [result],
  );
  const branches = useMemo(() => asRows(result?.data?.branch), [result]);

  async function runCollect() {
    if (!keyword.trim()) return;
    setLoading(true);
    setError("");
    try {
      const out = await api.collect({
        keyword: keyword.trim(),
        platform,
        dims,
        prefer_tier: preferTier,
        depth: 1,
      });
      setResult(out);
      setTab("basic");
      setPage("aiqicha");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runNeo4jImport(dryRun: boolean) {
    setLoading(true);
    setError("");
    try {
      const out = await api.importNeo4j(dryRun);
      setNeo4jProbe(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const whCounts = (warehouse?.counts ?? {}) as Record<string, number>;
  const neo4j = (doctor?.neo4j ?? {}) as Record<string, unknown>;
  const tiers = (doctor?.tiers ?? {}) as Record<string, Record<string, unknown>>;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">Enterprise Scout</div>
        <button className={`nav-btn ${page === "settings" ? "active" : ""}`} onClick={() => setPage("settings")}>
          设置
        </button>
        <button className={`nav-btn ${page === "aiqicha" ? "active" : ""}`} onClick={() => setPage("aiqicha")}>
          爱企查
        </button>
        <button className={`nav-btn ${page === "status" ? "active" : ""}`} onClick={() => setPage("status")}>
          状态 / 验收
        </button>
      </aside>

      <main className="main">
        {error ? <p className="error">{error}</p> : null}

        {page === "settings" ? (
          <>
            <section className="panel">
              <h2>数据仓库</h2>
              <div className="grid-2">
                <div className="stat">
                  <div className="label">路径</div>
                  <div className="value">{String(warehouse?.dir ?? "-")}</div>
                </div>
                <div className="stat">
                  <div className="label">实体 / 股东边 / 分支</div>
                  <div className="value">
                    {whCounts.entities_merged ?? 0} / {whCounts.holds_merged ?? 0} / {whCounts.branches_merged ?? 0}
                  </div>
                </div>
              </div>
            </section>
            <section className="panel">
              <h2>Neo4j</h2>
              <div className="grid-2">
                <div className="stat">
                  <div className="label">URI</div>
                  <div className="value">{String(neo4j.uri ?? "-")}</div>
                </div>
                <div className="stat">
                  <div className="label">连通性</div>
                  <div className={`value ${neo4jProbe?.ok ? "ok" : ""}`}>
                    {neo4jProbe?.ok ? "可达" : String(neo4jProbe?.error ?? "未探测")}
                  </div>
                </div>
              </div>
              <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
                <button className="primary" disabled={loading} onClick={() => void runNeo4jImport(true)}>
                  Dry-run 统计
                </button>
                <button className="primary" disabled={loading} onClick={() => void runNeo4jImport(false)}>
                  导入 Neo4j
                </button>
              </div>
            </section>
            <section className="panel">
              <h2>通道就绪</h2>
              <div className="grid-2">
                <div className="stat">
                  <div className="label">L1 GSXT</div>
                  <div className="value">{tiers.l1_registry?.available ? "可用" : "不可用"}</div>
                </div>
                <div className="stat">
                  <div className="label">L2 ENScan</div>
                  <div className="value">{tiers.l2_registry?.available ? "可用" : "不可用"}</div>
                </div>
              </div>
              <button className="primary" style={{ marginTop: "0.75rem" }} disabled={loading} onClick={() => void refreshSettings()}>
                刷新
              </button>
            </section>
          </>
        ) : null}

        {page === "aiqicha" ? (
          <>
            <section className="panel">
              <h2>企业查询</h2>
              <div className="query-row">
                <input
                  placeholder="公司名 / 关键词"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && void runCollect()}
                />
                <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                  <option value="aiqicha">爱企查</option>
                  <option value="gsxt">GSXT 官方</option>
                  <option value="tianyancha">天眼查</option>
                </select>
                <select value={preferTier} onChange={(e) => setPreferTier(e.target.value)}>
                  <option value="">默认 tier</option>
                  <option value="l1">L1 官方</option>
                  <option value="l2">L2 ENScan</option>
                  <option value="l3">L3 corpus</option>
                </select>
                <input
                  style={{ minWidth: 180 }}
                  value={dims}
                  onChange={(e) => setDims(e.target.value)}
                  placeholder="dims: registry,equity"
                />
                <button className="primary" disabled={loading || !keyword.trim()} onClick={() => void runCollect()}>
                  {loading ? "查询中…" : "查询"}
                </button>
              </div>
              {result ? (
                <p className="muted" style={{ marginTop: "0.75rem" }}>
                  grade={result.grade} channel={result.channel} tier={result.source_tier || "-"} — {result.message}
                </p>
              ) : null}
            </section>

            {result ? (
              <section className="panel">
                <div className="tabs">
                  {(
                    [
                      ["basic", "基本信息"],
                      ["holders", "股东"],
                      ["invest", "投资"],
                      ["branch", "分支机构"],
                      ["raw", "原始 JSON"],
                    ] as const
                  ).map(([id, label]) => (
                    <button key={id} className={`tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
                      {label}
                    </button>
                  ))}
                </div>
                {tab === "basic" ? (
                  <SimpleTable
                    rows={[info]}
                    columns={["name", "entName", "company_name", "credit_code", "uniscId", "reg_code", "pid"]}
                  />
                ) : null}
                {tab === "holders" ? <SimpleTable rows={holders} columns={["name", "scale", "ratio"]} /> : null}
                {tab === "invest" ? <SimpleTable rows={invests} columns={["name", "scale", "ratio"]} /> : null}
                {tab === "branch" ? <SimpleTable rows={branches} columns={["name", "scale"]} /> : null}
                {tab === "raw" ? <pre>{JSON.stringify(result.data, null, 2)}</pre> : null}
              </section>
            ) : null}
          </>
        ) : null}

        {page === "status" ? (
          <section className="panel">
            <h2>后端验收</h2>
            <p className={verify?.ok ? "ok" : "error"}>
              verify: {verify?.ok ? "通过" : "未通过"} {Array.isArray(verify?.failed) ? `(${verify.failed.join(", ")})` : ""}
            </p>
            <pre>{JSON.stringify(verify?.checks ?? {}, null, 2)}</pre>
          </section>
        ) : null}
      </main>
    </div>
  );
}
