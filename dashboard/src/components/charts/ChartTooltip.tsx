interface TooltipEntry {
  dataKey: string;
  name: string;
  value: number;
  color: string;
}

interface Props {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  formatValue?: (entry: TooltipEntry) => string;
}

export function ChartTooltip({ active, payload, label, formatValue }: Props) {
  if (!active || !payload?.length) return null;

  const defaultFormat = (entry: TooltipEntry) =>
    entry.dataKey === 'mpe' ? entry.value.toFixed(1) : `${entry.value}%`;

  return (
    <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
      <p
        className="text-[#6b7280] text-[10px] uppercase tracking-wider mb-1.5"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
      >
        {label}
      </p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2 mb-0.5">
          <div className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span
            className="text-[#9090a8] text-[10px]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {entry.name}:
          </span>
          <span
            className="text-white text-[10px]"
            style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}
          >
            {formatValue ? formatValue(entry) : defaultFormat(entry)}
          </span>
        </div>
      ))}
    </div>
  );
}
