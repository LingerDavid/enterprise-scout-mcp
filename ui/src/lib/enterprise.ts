import type { CollectResult } from "../api";

export function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((x) => x && typeof x === "object") as Record<string, unknown>[];
}

export function firstInfo(data: Record<string, unknown> | null): Record<string, unknown> {
  if (!data) return {};
  const info = data.enterprise_info;
  if (Array.isArray(info) && info[0] && typeof info[0] === "object") return info[0] as Record<string, unknown>;
  if (info && typeof info === "object") return info as Record<string, unknown>;
  return data;
}

function pick(sources: Record<string, unknown>[], keys: string[]): string {
  for (const src of sources) {
    for (const k of keys) {
      const v = src[k];
      if (v !== undefined && v !== null && String(v).trim()) return String(v).trim();
    }
  }
  return "";
}

export function companyTitle(info: Record<string, unknown>, keyword: string): string {
  return pick([info], ["name", "entName", "company_name", "企业名称"]) || keyword;
}

export type ProfileField = { label: string; value: string };

export function profileFields(info: Record<string, unknown>): ProfileField[] {
  const src = [info];
  const rows: ProfileField[] = [
    { label: "企业名称", value: pick(src, ["name", "entName", "company_name", "企业名称"]) },
    { label: "统一社会信用代码", value: pick(src, ["credit_code", "uniscId", "reg_code", "统一社会信用代码", "socialCreditCode"]) },
    { label: "法定代表人", value: pick(src, ["legal_person", "legalPerson", "operName", "法定代表人", "法人"]) },
    { label: "注册资本", value: pick(src, ["reg_capital", "regCapital", "注册资本", "capital"]) },
    { label: "成立日期", value: pick(src, ["establish_date", "establishDate", "成立日期", "startDate"]) },
    { label: "经营状态", value: pick(src, ["reg_status", "regStatus", "经营状态", "status"]) },
    { label: "所属行业", value: pick(src, ["industry", "行业", "industryName"]) },
    { label: "注册地址", value: pick(src, ["address", "reg_addr", "注册地址", "dom"]) },
    { label: "平台 ID", value: pick(src, ["pid", "aiqicha_id", "nameId", "entity_id"]) },
  ];
  return rows.filter((r) => r.value);
}

export function equityRows(result: CollectResult | null) {
  const data = result?.data ?? {};
  return {
    holders: asRows(data.partner).concat(asRows(data.stockholder)).concat(asRows(data.holder)),
    invests: asRows(data.invest).concat(asRows(data.holds)),
    branches: asRows(data.branch),
  };
}

export function tableColumns(rows: Record<string, unknown>[]): string[] {
  if (!rows.length) return ["name"];
  const preferred = ["name", "scale", "ratio", "percent", "amount", "status"];
  const keys = new Set<string>();
  for (const row of rows.slice(0, 5)) {
    Object.keys(row).forEach((k) => keys.add(k));
  }
  const ordered = preferred.filter((k) => keys.has(k));
  const rest = [...keys].filter((k) => !ordered.includes(k)).slice(0, 4);
  return [...ordered, ...rest];
}

export const COLUMN_LABELS: Record<string, string> = {
  name: "名称",
  scale: "比例",
  ratio: "持股比例",
  percent: "比例",
  amount: "金额",
  status: "状态",
  domain: "域名",
  site: "网站",
  icp: "备案号",
  web_name: "网站名称",
  title: "标题",
  version: "版本",
};

export type ResultTabDef = {
  id: string;
  label: string;
  rows: Record<string, unknown>[];
  columns: string[];
};

export function buildResultTabs(result: CollectResult | null): ResultTabDef[] {
  if (!result?.data) return [];
  const data = result.data;
  const { holders, invests, branches } = equityRows(result);
  const tabs: ResultTabDef[] = [
    {
      id: "basic",
      label: "基本信息",
      rows: [],
      columns: [],
    },
    {
      id: "holders",
      label: `股东(${holders.length})`,
      rows: holders,
      columns: tableColumns(holders),
    },
    {
      id: "invest",
      label: `投资(${invests.length})`,
      rows: invests,
      columns: tableColumns(invests),
    },
    {
      id: "branch",
      label: `分支机构(${branches.length})`,
      rows: branches,
      columns: tableColumns(branches),
    },
  ];

  const digital: [string, string, string][] = [
    ["icp", "备案信息", "icp"],
    ["app", "APP", "app"],
    ["wechat", "微信公众号", "wechat"],
    ["wx_app", "小程序", "wx_app"],
  ];
  for (const [key, label, field] of digital) {
    const rows = asRows(data[key]);
    if (rows.length) {
      tabs.push({ id: field, label: `${label}(${rows.length})`, rows, columns: tableColumns(rows) });
    }
  }

  tabs.push({ id: "raw", label: "原始 JSON", rows: [], columns: [] });
  return tabs;
}

export function topHoldersForStrip(holders: Record<string, unknown>[], limit = 6) {
  return holders.slice(0, limit).map((h) => ({
    name: String(h.name ?? h.entName ?? "—"),
    ratio: String(h.scale ?? h.ratio ?? h.percent ?? ""),
  }));
}
