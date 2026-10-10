import { useMemo, useState } from "react";
import type { CollectResult } from "../api";
import { DataTable } from "../components/DataTable";
import { ExportModal } from "../components/ExportModal";
import { HoldingTree } from "../components/HoldingTree";
import { StatusPill } from "../components/StatusPill";
import { buildHoldingTree } from "../lib/equityTree";
import {
  buildResultTabs,
  companyTitle,
  equityRows,
  firstInfo,
  profileFields,
  topHoldersForStrip,
} from "../lib/enterprise";

type Props = {
  keyword: string;
  platform: string;
  dims: string;
  preferTier: string;
  loading: boolean;
  result: CollectResult | null;
  onKeyword: (v: string) => void;
  onPlatform: (v: string) => void;
  onDims: (v: string) => void;
  onPreferTier: (v: string) => void;
  onSearch: () => void;
};

export function AiqichaPage({
  keyword,
  platform,
  dims,
  preferTier,
  loading,
  result,
  onKeyword,
  onPlatform,
  onDims,
  onPreferTier,
  onSearch,
}: Props) {
  const [tab, setTab] = useState("basic");
  const [exportOpen, setExportOpen] = useState(false);
  const info = useMemo(() => firstInfo(result?.data ?? null), [result]);
  const title = companyTitle(info, keyword);
  const tabs = useMemo(() => buildResultTabs(result), [result]);
  const { holders } = useMemo(() => equityRows(result), [result]);
  const strip = useMemo(() => topHoldersForStrip(holders), [holders]);
  const treeNodes = useMemo(() => buildHoldingTree(result, title), [result, title]);
  const active = tabs.find((t) => t.id === tab) ?? tabs[0];

  return (
    <div>
      <h1 className="page-title">爱企查</h1>

      <section className="search-hero">
        <div className="search-row">
          <input
            placeholder="输入企业名称 / 关键词，例如：北京百度网讯科技有限公司"
            value={keyword}
            onChange={(e) => onKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
          />
          <select value={platform} onChange={(e) => onPlatform(e.target.value)}>
            <option value="aiqicha">爱企查</option>
            <option value="gsxt">GSXT 官方</option>
            <option value="tianyancha">天眼查</option>
          </select>
          <select value={preferTier} onChange={(e) => onPreferTier(e.target.value)}>
            <option value="">默认 Tier</option>
            <option value="l1">L1 官方</option>
            <option value="l2">L2 ENScan</option>
            <option value="l3">L3 Corpus</option>
          </select>
          <input
            value={dims}
            onChange={(e) => onDims(e.target.value)}
            placeholder="registry,equity,digital"
            title="采集维度"
          />
          <button type="button" className="btn btn-primary" disabled={loading || !keyword.trim()} onClick={onSearch}>
            {loading ? (
              <>
                <span className="spinner" /> 查询中
              </>
            ) : (
              "查询"
            )}
          </button>
        </div>
      </section>

      {!result ? (
        <section className="card">
          <div className="empty">
            <div className="empty-icon">⌕</div>
            <div>输入企业名称开始查询</div>
            <div className="form-hint" style={{ marginTop: "0.35rem" }}>
              支持股东、投资、分支机构及备案等多 Tab 展示
            </div>
          </div>
        </section>
      ) : (
        <section className="card">
          <div className="company-banner">
            <div>
              <h2>{title}</h2>
              <div className="company-meta">
                <span>通道：{result.channel}</span>
                <span>Tier：{result.source_tier || "-"}</span>
                {result.message ? <span>{result.message}</span> : null}
              </div>
            </div>
            <div className="btn-row">
              <button type="button" className="btn btn-primary" onClick={() => setExportOpen(true)}>
                导出控股树
              </button>
              <StatusPill grade={result.grade} />
            </div>
          </div>

          <div className="card-body tree-panel">
            <HoldingTree nodes={treeNodes} companyName={title} />
          </div>

          {strip.length ? (
            <div className="equity-strip">
              <span className="form-hint" style={{ marginRight: "0.25rem" }}>股东穿透</span>
              {strip.map((h, i) => (
                <span key={i} className="equity-chip">
                  <strong>{h.ratio || "?"}</strong>
                  <span>{h.name}</span>
                </span>
              ))}
            </div>
          ) : null}

          <div className="result-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`result-tab ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="card-body" style={{ paddingTop: "0.85rem" }}>
            {tab === "basic" ? (
              <dl className="profile-grid">
                {profileFields(info).map((f) => (
                  <div key={f.label} className="profile-item">
                    <dt>{f.label}</dt>
                    <dd>{f.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {tab === "raw" ? <pre className="json-block">{JSON.stringify(result.data, null, 2)}</pre> : null}
            {tab !== "basic" && tab !== "raw" && active ? (
              <DataTable rows={active.rows} columns={active.columns} />
            ) : null}
          </div>
        </section>
      )}

      {result ? (
        <ExportModal
          open={exportOpen}
          result={result}
          keyword={keyword}
          onClose={() => setExportOpen(false)}
        />
      ) : null}
    </div>
  );
}
