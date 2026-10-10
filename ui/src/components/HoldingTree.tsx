import type { TreeNode } from "../lib/equityTree";

type Props = {
  nodes: TreeNode[];
  companyName: string;
};

export function HoldingTree({ nodes, companyName }: Props) {
  const holders = nodes.filter((n) => n.kind === "holder");
  const company = nodes.find((n) => n.kind === "company") ?? { id: "c", name: companyName, kind: "company" as const };
  const children = nodes.filter((n) => n.kind === "invest" || n.kind === "branch");

  if (!holders.length && !children.length) {
    return <p className="muted">暂无股权穿透数据，请使用 dims=registry,equity 查询</p>;
  }

  return (
    <div className="holding-tree">
      {holders.length ? (
        <div className="tree-tier tree-tier-up">
          {holders.map((h) => (
            <div key={h.id} className="tree-node tree-node-holder">
              <div className="tree-node-title">{h.name}</div>
              {h.ratio ? <div className="tree-node-ratio">{h.ratio}</div> : null}
              <div className="tree-connector-down" />
            </div>
          ))}
        </div>
      ) : null}

      <div className="tree-tier tree-tier-center">
        <div className="tree-node tree-node-company">
          <div className="tree-node-title">{company.name}</div>
        </div>
      </div>

      {children.length ? (
        <div className="tree-tier tree-tier-down">
          {children.map((c) => (
            <div key={c.id} className={`tree-node tree-node-${c.kind}`}>
              <div className="tree-connector-up" />
              <div className="tree-node-title">{c.name}</div>
              {c.ratio ? <div className="tree-node-ratio">{c.ratio}</div> : null}
              <div className="tree-node-tag">{c.kind === "branch" ? "分支" : "投资"}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
