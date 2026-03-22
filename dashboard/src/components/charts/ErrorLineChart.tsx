import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import type { SeasonChartPoint } from '../../types';
import { MPE_GOOD_THRESHOLD, MPE_POOR_THRESHOLD } from '../../utils/thresholds';

interface Props {
  chartData: SeasonChartPoint[];
}

export function ErrorLineChart({ chartData }: Props) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e1e30" vertical={false} />
        <XAxis
          dataKey="race"
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
          domain={[0, (dataMax: number) => Math.ceil(dataMax * 1.1)]}
          tick={{ fill: '#4a4a62', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            return (
              <div className="bg-[#131320] border border-[#2a2a40] rounded-lg px-3 py-2 shadow-xl">
                <p
                  className="text-[#6b7280] text-[10px] mb-1"
                  style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
                >
                  {label}
                </p>
                <span
                  className="text-white text-xs"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {(payload[0]?.value as number)?.toFixed(1)} avg positions off
                </span>
              </div>
            );
          }}
        />
        <ReferenceLine
          y={MPE_GOOD_THRESHOLD}
          stroke="#22c55e"
          strokeDasharray="4 2"
          strokeOpacity={0.5}
          label={{
            value: 'Good',
            fill: '#22c55e',
            fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        />
        <ReferenceLine
          y={MPE_POOR_THRESHOLD}
          stroke="#ef4444"
          strokeDasharray="4 2"
          strokeOpacity={0.5}
          label={{
            value: 'Poor',
            fill: '#ef4444',
            fontSize: 9,
            fontFamily: "'JetBrains Mono', monospace",
          }}
        />
        <Line
          type="monotone"
          dataKey="mpe"
          name="Mean Position Error"
          stroke="#f97316"
          strokeWidth={2}
          dot={{ fill: '#f97316', r: 4, strokeWidth: 0 }}
          activeDot={{ r: 6, fill: '#f97316' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
