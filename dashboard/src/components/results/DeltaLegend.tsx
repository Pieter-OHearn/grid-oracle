const DELTA_KEY = [
  { label: 'Exact', color: '#22c55e' },
  { label: '±1–2', color: '#eab308' },
  { label: '±3–4', color: '#f97316' },
  { label: '5+', color: '#ef4444' },
];

export function DeltaLegend() {
  return (
    <div className="flex items-center gap-4 mb-4">
      <span
        className="text-[#3a3a52] text-[10px] uppercase tracking-wider"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
      >
        Delta Key:
      </span>
      {DELTA_KEY.map((k) => (
        <div key={k.label} className="flex items-center gap-1.5">
          <div
            className="w-2.5 h-2.5 rounded"
            style={{ background: `${k.color}40`, border: `1px solid ${k.color}60` }}
          />
          <span
            className="text-[10px] text-[#6b7280]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {k.label}
          </span>
        </div>
      ))}
    </div>
  );
}
