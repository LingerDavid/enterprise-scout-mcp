export function StatusPill({ grade }: { grade: string }) {
  const g = grade.toLowerCase();
  const cls =
    g === "ok" ? "pill pill-ok" : g === "partial" ? "pill pill-warn" : g ? "pill pill-bad" : "pill pill-neutral";
  const label = g === "ok" ? "成功" : g === "partial" ? "部分" : g || "未知";
  return <span className={cls}>{label}</span>;
}

export function BoolPill({ ok, yes = "可用", no = "不可用" }: { ok: boolean; yes?: string; no?: string }) {
  return <span className={`pill ${ok ? "pill-ok" : "pill-neutral"}`}>{ok ? yes : no}</span>;
}
