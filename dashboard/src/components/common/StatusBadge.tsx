type Status = 'completed' | 'next' | 'upcoming';

const BADGE_STYLES: Record<Status, { className: string; label: string }> = {
  completed: {
    className:
      "px-2 py-0.5 bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded text-[10px] uppercase tracking-wider",
    label: 'Completed',
  },
  next: {
    className:
      "px-2 py-0.5 bg-[#e10600]/20 text-[#e10600] border border-[#e10600]/40 rounded text-[10px] uppercase tracking-wider",
    label: 'Next Race',
  },
  upcoming: {
    className:
      "px-2 py-0.5 bg-[#1e1e30] text-[#6b7280] rounded text-[10px] uppercase tracking-wider",
    label: 'Upcoming',
  },
};

interface Props {
  status: Status;
}

export function StatusBadge({ status }: Props) {
  const { className, label } = BADGE_STYLES[status];
  return (
    <span
      className={className}
      style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 700 }}
    >
      {label}
    </span>
  );
}
