import { CONSTRUCTOR_COLORS, CONSTRUCTOR_SHORT } from '../../data';

interface Props {
  constructor: string;
  showDot?: boolean;
}

export function ConstructorBadge({ constructor, showDot = true }: Props) {
  const color = CONSTRUCTOR_COLORS[constructor] ?? '#6b7280';
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      {showDot && <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />}
      <span
        className="text-[#6b7280] text-[10px] truncate"
        style={{ fontFamily: "'Barlow Condensed', sans-serif", fontWeight: 600 }}
      >
        {CONSTRUCTOR_SHORT[constructor] ?? constructor}
      </span>
    </div>
  );
}
