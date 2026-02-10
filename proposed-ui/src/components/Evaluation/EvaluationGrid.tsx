import { EvaluationDimension } from "../../types/domain";
import { EvaluationCard } from "./EvaluationCard";

export function EvaluationGrid(props: { dims: EvaluationDimension[] }) {
  return (
    <div className="eval-grid">
      {props.dims.map((d) => (
        <EvaluationCard key={d.dimensionKey + d.label} dim={d} />
      ))}
    </div>
  );
}
