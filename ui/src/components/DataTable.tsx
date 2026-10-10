import { COLUMN_LABELS } from "../lib/enterprise";

type Props = {
  rows: Record<string, unknown>[];
  columns: string[];
  emptyText?: string;
};

export function DataTable({ rows, columns, emptyText = "暂无数据" }: Props) {
  if (!rows.length) {
    return (
      <div className="empty">
        <div className="empty-icon">∅</div>
        <div>{emptyText}</div>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            {columns.map((c) => (
              <th key={c}>{COLUMN_LABELS[c] ?? c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
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
