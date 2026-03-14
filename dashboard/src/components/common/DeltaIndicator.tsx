import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

function getDeltaColor(delta: number): string {
  if (delta === 0) return '#22c55e';
  if (Math.abs(delta) <= 2) return '#eab308';
  if (Math.abs(delta) <= 4) return '#f97316';
  return '#ef4444';
}

interface Props {
  delta: number;
}

export function DeltaIndicator({ delta }: Props) {
  const color = getDeltaColor(delta);
  return (
    <div className="flex flex-col items-center justify-center gap-0.5">
      {delta === 0 ? (
        <Minus size={14} style={{ color }} />
      ) : delta > 0 ? (
        <TrendingDown size={14} style={{ color }} />
      ) : (
        <TrendingUp size={14} style={{ color }} />
      )}
      <span
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.6rem',
          color,
          fontWeight: 600,
        }}
      >
        {delta === 0 ? '=' : delta > 0 ? `+${delta}` : `${delta}`}
      </span>
    </div>
  );
}
