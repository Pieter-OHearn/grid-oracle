interface Props {
  label: string;
  value: string;
  sub?: string;
  icon?: string;
  color?: string;
}

export function StatCard({ label, value, sub, icon, color = '#e10600' }: Props) {
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-4 text-center hover:border-[#2a2a40] transition-colors">
      {icon && <div className="text-xl mb-1">{icon}</div>}
      <div
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: '1.7rem',
          fontWeight: 800,
          color,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        className="text-[#3a3a52] text-[10px] mt-1 uppercase tracking-wider"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
      >
        {label}
      </div>
      {sub && (
        <div
          className="text-[#2e2e45] text-[9px] mt-0.5"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
