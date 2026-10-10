import type { CollectResult } from "../api";
import { asRows, companyTitle, equityRows, firstInfo } from "./enterprise";

export type TreeNode = {
  id: string;
  name: string;
  ratio?: string;
  kind: "holder" | "company" | "invest" | "branch";
};

export type ExportOptions = {
  includeHolders: boolean;
  includeInvests: boolean;
  includeBranches: boolean;
  includeIcp: boolean;
  minRatio: number;
  maxDepth: number;
};

export function parseRatio(text: unknown): number | null {
  if (text === undefined || text === null) return null;
  const raw = String(text).replace("%", "").trim();
  const m = raw.match(/([\d.]+)/);
  if (!m) return null;
  const val = parseFloat(m[1]);
  if (!Number.isFinite(val) || val <= 0) return null;
  return val <= 1 ? val * 100 : val;
}

export function filterByMinRatio(rows: Record<string, unknown>[], minRatio: number): Record<string, unknown>[] {
  if (minRatio <= 0) return rows;
  return rows.filter((row) => {
    const pct = parseRatio(row.scale ?? row.ratio ?? row.percent);
    return pct === null || pct >= minRatio;
  });
}

export function buildHoldingTree(result: CollectResult | null, companyName: string, minRatio = 0): TreeNode[] {
  if (!result) return [];
  const center: TreeNode = { id: "company", name: companyName, kind: "company" };
  const { holders, invests, branches } = equityRows(result);
  const nodes: TreeNode[] = [];

  for (const h of filterByMinRatio(holders, minRatio)) {
    nodes.push({
      id: `h-${String(h.name ?? "")}`,
      name: String(h.name ?? h.entName ?? "—"),
      ratio: String(h.scale ?? h.ratio ?? h.percent ?? ""),
      kind: "holder",
    });
  }
  nodes.push(center);
  if (minRatio <= 0 || invests.length) {
    for (const inv of filterByMinRatio(invests, minRatio)) {
      nodes.push({
        id: `i-${String(inv.name ?? "")}`,
        name: String(inv.name ?? "—"),
        ratio: String(inv.scale ?? inv.ratio ?? inv.percent ?? ""),
        kind: "invest",
      });
    }
  }
  for (const b of branches) {
    nodes.push({
      id: `b-${String(b.name ?? "")}`,
      name: String(b.name ?? "—"),
      kind: "branch",
    });
  }
  return nodes;
}

export function defaultExportOptions(result: CollectResult | null): ExportOptions {
  const data = result?.data ?? {};
  const { holders, invests, branches } = equityRows(result);
  return {
    includeHolders: holders.length > 0,
    includeInvests: invests.length > 0,
    includeBranches: branches.length > 0,
    includeIcp: asRows(data.icp).length > 0,
    minRatio: 0,
    maxDepth: 1,
  };
}

export function buildExportPayload(
  result: CollectResult,
  keyword: string,
  opts: ExportOptions,
): Record<string, unknown> {
  const info = firstInfo(result.data ?? null);
  const title = companyTitle(info, keyword);
  const data = result.data ?? {};
  const { holders, invests, branches } = equityRows(result);
  const payload: Record<string, unknown> = {
    company: title,
    pid: info.pid ?? info.aiqicha_id ?? info.nameId ?? "",
    keyword,
    grade: result.grade,
    channel: result.channel,
    exported_at: new Date().toISOString(),
    filters: { min_ratio: opts.minRatio, max_depth: opts.maxDepth },
    enterprise_info: info,
  };
  if (opts.includeHolders) payload.holders = filterByMinRatio(holders, opts.minRatio);
  if (opts.includeInvests) payload.invests = filterByMinRatio(invests, opts.minRatio);
  if (opts.includeBranches) payload.branches = branches;
  if (opts.includeIcp) payload.icp = asRows(data.icp);
  return payload;
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
