import type { EvaluationBundle } from '../../types';
import { EvaluationCard } from './EvaluationCard';
import { OverallLabelBadge } from './OverallLabelBadge';

interface EvaluationGridProps {
  bundle: EvaluationBundle;
}

export function EvaluationGrid({ bundle }: EvaluationGridProps) {
  return (
    <div>
      {/* Overall label header */}
      <div className="mb-4 flex items-center gap-3">
        <h3 className="text-sm font-medium text-[var(--text-secondary)]">
          Overall Assessment
        </h3>
        <OverallLabelBadge label={bundle.overallLabel} />
      </div>

      {/* Grid of dimension cards */}
      <div className="grid gap-3 sm:grid-cols-1 md:grid-cols-2">
        {bundle.dimensions.map((dim) => (
          <EvaluationCard key={`${dim.dimensionKey}-${dim.label}`} dimension={dim} />
        ))}
      </div>
    </div>
  );
}
