import { useCallback, useEffect, useState } from "react";
import { api, type CollectResult } from "./api";
import { TopNav, type PageId } from "./components/TopNav";
import { AiqichaPage } from "./pages/AiqichaPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StatusPage } from "./pages/StatusPage";

type SettingsSection = "global" | "warehouse" | "neo4j" | "channels" | "sessions";

export default function App() {
  const [page, setPage] = useState<PageId>("aiqicha");
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("global");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [backendOk, setBackendOk] = useState(false);

  const [doctor, setDoctor] = useState<Record<string, unknown> | null>(null);
  const [warehouse, setWarehouse] = useState<Record<string, unknown> | null>(null);
  const [verify, setVerify] = useState<Record<string, unknown> | null>(null);
  const [neo4jProbe, setNeo4jProbe] = useState<Record<string, unknown> | null>(null);
  const [sessions, setSessions] = useState<Record<string, unknown> | null>(null);

  const [keyword, setKeyword] = useState("");
  const [platform, setPlatform] = useState("aiqicha");
  const [dims, setDims] = useState("registry,equity,digital");
  const [preferTier, setPreferTier] = useState("");
  const [result, setResult] = useState<CollectResult | null>(null);

  const refreshMeta = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [health, d, w, v, n, sess] = await Promise.all([
        api.health(),
        api.doctor(false),
        api.warehouse(),
        api.verify(),
        api.neo4jProbe(),
        api.sessions(),
      ]);
      setBackendOk(Boolean(health.ok));
      setDoctor(d);
      setWarehouse(w);
      setVerify(v);
      setNeo4jProbe(n);
      setSessions(sess.sessions ?? sess);
    } catch (e) {
      setBackendOk(false);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMeta();
  }, [refreshMeta]);

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

  return (
    <div className="shell">
      <TopNav page={page} onChange={setPage} backendOk={backendOk} />
      <main className="content">
        {error ? <div className="alert alert-error">{error}</div> : null}

        {page === "settings" ? (
          <SettingsPage
            section={settingsSection}
            onSection={setSettingsSection}
            warehouse={warehouse}
            doctor={doctor}
            neo4jProbe={neo4jProbe}
            sessions={sessions}
            loading={loading}
            onRefresh={() => void refreshMeta()}
            onNeo4jImport={(dry) => void runNeo4jImport(dry)}
          />
        ) : null}

        {page === "aiqicha" ? (
          <AiqichaPage
            keyword={keyword}
            platform={platform}
            dims={dims}
            preferTier={preferTier}
            loading={loading}
            result={result}
            onKeyword={setKeyword}
            onPlatform={setPlatform}
            onDims={setDims}
            onPreferTier={setPreferTier}
            onSearch={() => void runCollect()}
          />
        ) : null}

        {page === "status" ? (
          <StatusPage verify={verify} loading={loading} onRefresh={() => void refreshMeta()} />
        ) : null}
      </main>
    </div>
  );
}
