import { BoolPill } from "../components/StatusPill";

type SettingsSection = "global" | "warehouse" | "neo4j" | "channels";

type Props = {
  section: SettingsSection;
  onSection: (s: SettingsSection) => void;
  warehouse: Record<string, unknown> | null;
  doctor: Record<string, unknown> | null;
  neo4jProbe: Record<string, unknown> | null;
  loading: boolean;
  onRefresh: () => void;
  onNeo4jImport: (dryRun: boolean) => void;
};

const SECTIONS: { id: SettingsSection; label: string }[] = [
  { id: "global", label: "全局设置" },
  { id: "warehouse", label: "数据仓库" },
  { id: "neo4j", label: "Neo4j" },
  { id: "channels", label: "采集通道" },
];

export function SettingsPage({
  section,
  onSection,
  warehouse,
  doctor,
  neo4jProbe,
  loading,
  onRefresh,
  onNeo4jImport,
}: Props) {
  const whCounts = (warehouse?.counts ?? {}) as Record<string, number>;
  const neo4j = (doctor?.neo4j ?? {}) as Record<string, unknown>;
  const tiers = (doctor?.tiers ?? {}) as Record<string, Record<string, unknown>>;
  const routing = (doctor?.routing ?? {}) as Record<string, unknown>;

  return (
    <div>
      <h1 className="page-title">设置</h1>
      <div className="layout-settings">
        <aside className="side-nav">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`side-nav-btn ${section === s.id ? "active" : ""}`}
              onClick={() => onSection(s.id)}
            >
              {s.label}
            </button>
          ))}
        </aside>

        <div>
          {section === "global" ? (
            <section className="card">
              <div className="card-header">
                <h3>全局设置</h3>
                <button type="button" className="btn" disabled={loading} onClick={onRefresh}>
                  刷新状态
                </button>
              </div>
              <div className="card-body form-grid">
                <div className="form-row">
                  <label>路由策略</label>
                  <div>
                    <input readOnly value={String(routing.source_policy ?? "ensan_only")} />
                    <div className="form-hint">工商主路径仅走 ENScan；L1 GSXT 需 prefer-tier=l1</div>
                  </div>
                </div>
                <div className="form-row">
                  <label>项目根目录</label>
                  <input readOnly value={String(doctor?.project_root ?? "-")} />
                </div>
                <div className="form-row">
                  <label>默认维度</label>
                  <input readOnly value="registry,equity" />
                  <div className="form-hint">可在爱企查页自定义 dims 参数</div>
                </div>
              </div>
            </section>
          ) : null}

          {section === "warehouse" ? (
            <section className="card">
              <div className="card-header">
                <h3>数据仓库</h3>
              </div>
              <div className="card-body">
                <div className="kpi-grid">
                  <div className="kpi">
                    <div className="kpi-label">实体行</div>
                    <div className="kpi-value">{whCounts.entities_merged ?? 0}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">股权边</div>
                    <div className="kpi-value">{whCounts.holds_merged ?? 0}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">分支边</div>
                    <div className="kpi-value">{whCounts.branches_merged ?? 0}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">补充数据</div>
                    <div className="kpi-value">{whCounts.supplements_merged ?? 0}</div>
                    <div className="kpi-sub">L3 / judicial corpus</div>
                  </div>
                </div>
                <div className="form-row" style={{ marginTop: "1rem" }}>
                  <label>路径</label>
                  <input readOnly value={String(warehouse?.dir ?? "-")} />
                </div>
              </div>
            </section>
          ) : null}

          {section === "neo4j" ? (
            <section className="card">
              <div className="card-header">
                <h3>Neo4j 图数据库</h3>
              </div>
              <div className="card-body form-grid">
                <div className="form-row">
                  <label>URI</label>
                  <input readOnly value={String(neo4j.uri ?? "bolt://127.0.0.1:7687")} />
                </div>
                <div className="form-row">
                  <label>连通性</label>
                  <div>
                    <BoolPill ok={Boolean(neo4jProbe?.ok)} yes="可达" no={String(neo4jProbe?.error ?? "未探测")} />
                    <div className="form-hint">EnterpriseLake docker compose 默认端口 7687</div>
                  </div>
                </div>
                <div className="btn-row">
                  <button type="button" className="btn" disabled={loading} onClick={() => onNeo4jImport(true)}>
                    Dry-run 统计
                  </button>
                  <button type="button" className="btn btn-primary" disabled={loading} onClick={() => onNeo4jImport(false)}>
                    导入 Neo4j
                  </button>
                </div>
                {neo4jProbe && "entities_merged" in neo4jProbe ? (
                  <div className="form-hint">
                    上次导入：实体 {String(neo4jProbe.entities_merged)} / 股东边 {String(neo4jProbe.holds_merged)} / 分支{" "}
                    {String(neo4jProbe.branches_merged)}
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          {section === "channels" ? (
            <section className="card">
              <div className="card-header">
                <h3>采集通道</h3>
              </div>
              <div className="card-body">
                <div className="kpi-grid">
                  <div className="kpi">
                    <div className="kpi-label">L1 GSXT 官方</div>
                    <div className="kpi-value" style={{ fontSize: "1rem" }}>
                      <BoolPill ok={Boolean(tiers.l1_registry?.available)} />
                    </div>
                    <div className="kpi-sub">{String(tiers.l1_registry?.session_mode ?? "")}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">L2 ENScan</div>
                    <div className="kpi-value" style={{ fontSize: "1rem" }}>
                      <BoolPill ok={Boolean(tiers.l2_registry?.available)} />
                    </div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">L3 Corpus</div>
                    <div className="kpi-value" style={{ fontSize: "1rem" }}>
                      <BoolPill ok={Boolean(tiers.l3?.available)} />
                    </div>
                    <div className="kpi-sub">文件 {String(tiers.l3?.corpus_files ?? 0)}</div>
                  </div>
                  <div className="kpi">
                    <div className="kpi-label">Handaas 征信</div>
                    <div className="kpi-value" style={{ fontSize: "1rem" }}>
                      <BoolPill ok={tiers.credit?.channel === "handaas_api"} yes="已配置" no="deferred" />
                    </div>
                  </div>
                </div>
                <p className="form-hint" style={{ marginTop: "0.75rem" }}>
                  爱企查 Cookie / GSXT Session 通过 escout sessions 管理；使用代理池可降低人机检测触发率。
                </p>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
