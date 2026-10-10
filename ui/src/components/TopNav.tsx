export type PageId = "settings" | "aiqicha" | "status";

const ITEMS: { id: PageId; label: string }[] = [
  { id: "settings", label: "设置" },
  { id: "aiqicha", label: "爱企查" },
  { id: "status", label: "验收" },
];

type Props = {
  page: PageId;
  onChange: (page: PageId) => void;
  backendOk?: boolean;
};

export function TopNav({ page, onChange, backendOk }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <div className="brand-mark">ES</div>
          <span>Enterprise Scout</span>
        </div>
        <nav className="topnav">
          {ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`topnav-btn ${page === item.id ? "active" : ""}`}
              onClick={() => onChange(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="topbar-meta">
          <span className={`pill ${backendOk ? "pill-ok" : "pill-neutral"}`}>
            {backendOk ? "后端在线" : "连接中"}
          </span>
        </div>
      </div>
    </header>
  );
}
