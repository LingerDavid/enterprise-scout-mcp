import { useEffect, useState } from "react";
import type { CollectResult } from "../api";
import { companyTitle, equityRows, firstInfo, asRows } from "../lib/enterprise";
import {
  buildExportPayload,
  defaultExportOptions,
  downloadJson,
  type ExportOptions,
} from "../lib/equityTree";

type Props = {
  open: boolean;
  result: CollectResult;
  keyword: string;
  onClose: () => void;
};

export function ExportModal({ open, result, keyword, onClose }: Props) {
  const info = firstInfo(result.data ?? null);
  const title = companyTitle(info, keyword);
  const pid = String(info.pid ?? info.aiqicha_id ?? info.nameId ?? "");
  const { holders, invests, branches } = equityRows(result);
  const icpCount = asRows(result.data?.icp).length;

  const [opts, setOpts] = useState<ExportOptions>(() => defaultExportOptions(result));

  useEffect(() => {
    if (open) setOpts(defaultExportOptions(result));
  }, [open, result]);

  if (!open) return null;

  function toggle(key: keyof ExportOptions) {
    setOpts((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function confirm() {
    const payload = buildExportPayload(result, keyword, opts);
    const safe = title.replace(/[^\w\u4e00-\u9fff-]+/g, "_").slice(0, 40);
    downloadJson(`${safe || "export"}_holding_tree.json`, payload);
    onClose();
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>控股树导出</h3>
          <button type="button" className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body form-grid">
          <div className="form-row">
            <label>企业名称</label>
            <input readOnly value={title} />
          </div>
          {pid ? (
            <div className="form-row">
              <label>PID</label>
              <input readOnly value={pid} />
            </div>
          ) : null}
          <div className="form-row">
            <label>导出内容</label>
            <div className="check-list">
              <label className="check-line">
                <input type="checkbox" checked={opts.includeHolders} onChange={() => toggle("includeHolders")} />
                股东信息({holders.length})
              </label>
              <label className="check-line">
                <input type="checkbox" checked={opts.includeInvests} onChange={() => toggle("includeInvests")} />
                对外投资({invests.length})
              </label>
              <label className="check-line">
                <input type="checkbox" checked={opts.includeBranches} onChange={() => toggle("includeBranches")} />
                分支机构({branches.length})
              </label>
              <label className="check-line">
                <input type="checkbox" checked={opts.includeIcp} disabled={!icpCount} onChange={() => toggle("includeIcp")} />
                备案信息({icpCount})
              </label>
            </div>
          </div>
          <div className="form-row">
            <label>控股比例</label>
            <div className="range-row">
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={opts.minRatio}
                onChange={(e) => setOpts((p) => ({ ...p, minRatio: Number(e.target.value) }))}
              />
              <span className="muted">% 及以上</span>
            </div>
          </div>
          <div className="form-row">
            <label>导出层级</label>
            <input
              type="number"
              min={1}
              max={5}
              value={opts.maxDepth}
              onChange={(e) => setOpts((p) => ({ ...p, maxDepth: Number(e.target.value) }))}
            />
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={confirm}>确定导出 JSON</button>
        </div>
      </div>
    </div>
  );
}
