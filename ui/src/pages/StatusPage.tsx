import { BoolPill } from "../components/StatusPill";

const LABELS: Record<string, string> = {
  persona_engine: "人设引擎",
  risk_routing: "风控路由",
  behavior: "行为配额",
  consistency: "一致性校验",
  disguise_egress: "TLS 伪装出口",
  captcha_branch: "验证码分支",
  l1_registry: "L1 工商官方",
  l2_registry: "L2 ENScan",
  l3_corpus: "L3 语料",
  equity_dimension: "股权维度",
  neo4j_warehouse_dry_run: "Warehouse 统计",
  neo4j_supplements: "Neo4j Supplement",
  neo4j_conflicts: "Neo4j Conflict",
  neo4j_model: "Neo4j 图模型",
  fine_ui: "Fine UI",
};

type Props = {
  verify: Record<string, unknown> | null;
  onRefresh: () => void;
  loading: boolean;
};

export function StatusPage({ verify, onRefresh, loading }: Props) {
  const checks = (verify?.checks ?? {}) as Record<string, boolean>;
  const failed = (verify?.failed ?? []) as string[];
  const counts = (verify?.warehouse_counts ?? {}) as Record<string, number>;

  return (
    <div>
      <h1 className="page-title">验收</h1>

      <section className="card">
        <div className="card-header">
          <h3>后端 checklist</h3>
          <button type="button" className="btn" disabled={loading} onClick={onRefresh}>
            重新检测
          </button>
        </div>
        <div className="card-body">
          <div style={{ marginBottom: "1rem" }}>
            <BoolPill ok={Boolean(verify?.ok)} yes="全部通过" no={`未通过 (${failed.length})`} />
            {verify?.note ? <div className="form-hint" style={{ marginTop: "0.35rem" }}>{String(verify.note)}</div> : null}
          </div>

          <div className="kpi-grid" style={{ marginBottom: "1rem" }}>
            <div className="kpi">
              <div className="kpi-label">实体</div>
              <div className="kpi-value">{counts.entities_merged ?? 0}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">股权边</div>
              <div className="kpi-value">{counts.holds_merged ?? 0}</div>
            </div>
            <div className="kpi">
              <div className="kpi-label">分支</div>
              <div className="kpi-value">{counts.branches_merged ?? 0}</div>
            </div>
          </div>

          <div className="check-grid">
            {Object.entries(checks).map(([key, ok]) => (
              <div key={key} className="check-item">
                <span>{LABELS[key] ?? key}</span>
                <BoolPill ok={ok} yes="✓" no="✗" />
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
