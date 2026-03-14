import { useParams } from 'react-router';
import { AlertCircle } from 'lucide-react';
import { RACES, RACE_PREDICTIONS } from '../data';
import { RaceHero } from '../components/prediction/RaceHero';
import { PodiumPreview } from '../components/prediction/PodiumPreview';
import { FullGridTable } from '../components/prediction/FullGridTable';

export function PredictionPage() {
  const { raceId } = useParams();
  const race = RACES.find((r) => r.id === raceId);
  const predictions = raceId ? RACE_PREDICTIONS[raceId] : null;

  if (!race) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <div className="text-center">
          <AlertCircle size={40} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Race not found</p>
        </div>
      </div>
    );
  }

  if (!predictions) {
    return (
      <div className="flex items-center justify-center h-full text-[#6b7280]">
        <p className="text-sm">No prediction data available for this race.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <RaceHero race={race} predictions={predictions} />
      <PodiumPreview predictions={predictions} />
      <FullGridTable predictions={predictions} />
    </div>
  );
}
