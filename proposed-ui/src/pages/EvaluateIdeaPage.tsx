import { useMemo, useState } from "react";
import { Card } from "../components/Card";
import { EvaluationGrid } from "../components/Evaluation/EvaluationGrid";
import { Badge } from "../components/Badge";

export function EvaluateIdeaPage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [entry, setEntry] = useState(185);
  const [stop, setStop] = useState(182);
  const [target, setTarget] = useState(190);

  const evalDims = useMemo(() => {
    const rr = Math.abs((target - entry) / (entry - stop || 1));
    return [
      {
        dimensionKey: "risk_structure",
        severity: rr < 1.2 ? "medium" : "low",
        label: rr < 1.2 ? "R:R is tight" : "Risk defined",
        explanation: rr < 1.2 ? "Reward relative to risk is modest. Consider whether the thesis justifies it." : "Stop and target are defined; sizing can be computed safely.",
        visuals: { type: "risk_shape", rr: Number.isFinite(rr) ? rr.toFixed(2) : "n/a" },
      },
      {
        dimensionKey: "strategy_consistency",
        severity: "info",
        label: "Needs strategy tag",
        explanation: "Add a strategy tag (pullback/breakout/etc.) to compare against your historical style.",
      },
      {
        dimensionKey: "regime_fit",
        severity: "info",
        label: "Regime fit pending",
        explanation: "Regime evaluation will use your market snapshot at the planned entry time.",
      },
    ] as any;
  }, [entry, stop, target]);

  return (
    <div className="stack">
      <Card title="Evaluate a Proposed Trade" right={<Badge text="Proposed" tone="info" />}>
        <div className="grid2">
          <div className="stack">
            <div className="field">
              <label>Symbol</label>
              <input className="input" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
            </div>
            <div className="field">
              <label>Direction</label>
              <select value={direction} onChange={(e) => setDirection(e.target.value as any)}>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </div>
            <div className="grid3">
              <div className="field">
                <label>Entry</label>
                <input type="number" value={entry} onChange={(e) => setEntry(Number(e.target.value))} />
              </div>
              <div className="field">
                <label>Stop</label>
                <input type="number" value={stop} onChange={(e) => setStop(Number(e.target.value))} />
              </div>
              <div className="field">
                <label>Target</label>
                <input type="number" value={target} onChange={(e) => setTarget(Number(e.target.value))} />
              </div>
            </div>
          </div>

          <div>
            <div className="muted small">Evaluation Snapshot</div>
            <EvaluationGrid dims={evalDims} />
          </div>
        </div>
      </Card>
    </div>
  );
}
