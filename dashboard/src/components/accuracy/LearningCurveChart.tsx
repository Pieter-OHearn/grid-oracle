import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { TrendingDown } from 'lucide-react';
import { ChartTooltip } from '../charts/ChartTooltip';
import type { LearningCurvePoint } from '../../types';

interface Props {
  data: LearningCurvePoint[];
}

export function LearningCurveChart({ data }: Props) {
  const maeDomain: [number, number] =
    data.length >= 2
      ? [
          Math.max(0, Math.min(...data.map((d) => d.mae)) - 0.5),
          Math.max(...data.map((d) => d.mae)) + 0.5,
        ]
      : [0, 5];

  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e30] rounded-xl p-5 mb-4">
      <div className="flex items-center gap-2 mb-5">
        <TrendingDown size={13} className="text-[#e10600]" />
        <h2
          className="text-xs uppercase tracking-wider text-[#6b7280]"
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontWeight: 700,
            letterSpacing: '0.1em',
          }}
        >
          Model Learning Curve
        </h2>
      </div>

      <div className="h-44">
        {data.length < 2 ? (
          <div className="h-full flex items-center justify-center">
            <p
              className="text-[#3a3a52] text-xs"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              Needs at least 2 completed rounds to display.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
              <XAxis
                dataKey="round"
                tickFormatter={(v) => `R${v}`}
                tick={{
                  fill: '#4a4a62',
                  fontSize: 10,
                  fontFamily: "'Barlow Condensed', sans-serif",
                  fontWeight: 600,
                }}
                axisLine={{ stroke: '#1e1e30' }}
                tickLine={false}
              />
              <YAxis
                domain={maeDomain}
                tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => v.toFixed(1)}
              />
              <Tooltip
                content={
                  <ChartTooltip
                    labelFormatter={(v) => `Round ${v}`}
                    formatValue={(entry) => entry.value.toFixed(2)}
                  />
                }
              />
              <Line
                type="monotone"
                dataKey="mae"
                name="MAE"
                stroke="#e10600"
                strokeWidth={2}
                dot={{ fill: '#e10600', r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: '#e10600' }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
