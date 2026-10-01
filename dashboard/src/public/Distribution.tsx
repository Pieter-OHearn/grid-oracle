import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import type { PublicEntry } from './contract';
import { Panel } from '../design-system/Panel';

export default function Distribution({ entries }: { entries: PublicEntry[] }) {
  const known = entries.filter((entry) => entry.win_probability !== null);
  return (
    <Panel
      title="Published win probability distribution"
      note="The table above provides the same data for keyboard and screen-reader access."
    >
      <div className="go-chart" aria-hidden="true">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={known.map((entry) => ({
              name: entry.driver_name ?? 'Unknown driver',
              probability: entry.win_probability! * 100,
            }))}
          >
            <CartesianGrid vertical={false} />
            <XAxis dataKey="name" hide />
            <YAxis unit="%" domain={[0, 100]} />
            <Bar dataKey="probability" fill="var(--go-accent)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
