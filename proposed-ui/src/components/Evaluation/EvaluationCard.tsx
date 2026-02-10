import { useState } from "react";
import { EvaluationDimension, Severity } from "../../types/domain";
import { Badge } from "../Badge";

function toneFromSeverity(s: Severity) {
  if (s === "high") return "danger";
  if (s === "medium") return "warn";
  if (s === "low") return "info";
  return "neutral";
}

export function EvaluationCard(props: { dim: EvaluationDimension }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="eval-card">
      <div className="eval-head" onClick={() => setOpen((v) => !v)} role="button" tabIndex={0}>
        <div>
          <div className="eval-title">{props.dim.label}</div>
          <div className="eval-sub">{props.dim.dimensionKey.replaceAll("_", " ")}</div>
        </div>
        <Badge text={props.dim.severity} tone={toneFromSeverity(props.dim.severity)} />
      </div>

      {open && (
        <div className="eval-body">
          <p className="muted">{props.dim.explanation}</p>
          {props.dim.visuals && (
            <div className="visual-placeholder">
              <div className="muted">Visual placeholder</div>
              <code>{JSON.stringify(props.dim.visuals, null, 2)}</code>
            </div>
          )}
          {props.dim.evidence && (
            <details>
              <summary>Evidence</summary>
              <pre>{JSON.stringify(props.dim.evidence, null, 2)}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
