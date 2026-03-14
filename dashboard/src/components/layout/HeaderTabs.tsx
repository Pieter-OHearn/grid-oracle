import { NavLink } from 'react-router';
import type { Race } from '../../types';

interface Props {
  race: Race;
}

const tabStyle = {
  fontFamily: "'Barlow Condensed', sans-serif",
  fontWeight: 600,
  letterSpacing: '0.06em',
  textTransform: 'uppercase' as const,
};

export function HeaderTabs({ race }: Props) {
  return (
    <div className="flex items-center gap-1">
      <NavLink
        to={`/race/${race.id}`}
        end
        className={({ isActive }) =>
          `px-3 py-1.5 rounded text-xs transition-all duration-150 ${
            isActive ? 'bg-[#e10600] text-white' : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
          }`
        }
        style={tabStyle}
      >
        Prediction
      </NavLink>
      {race.status === 'completed' && (
        <NavLink
          to={`/race/${race.id}/results`}
          className={({ isActive }) =>
            `px-3 py-1.5 rounded text-xs transition-all duration-150 ${
              isActive ? 'bg-[#e10600] text-white' : 'text-[#6b7280] hover:text-white hover:bg-[#1e1e30]'
            }`
          }
          style={tabStyle}
        >
          Results
        </NavLink>
      )}
    </div>
  );
}
